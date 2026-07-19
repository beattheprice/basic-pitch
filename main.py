import os, tempfile, traceback, asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from basic_pitch.inference import predict
from basic_pitch import build_icassp_2022_model_path, FilenameSuffix

# IMPORTANT: basic_pitch's auto-detected ICASSP_2022_MODEL_PATH picks a
# backend by priority (TF > CoreML > TFLite > ONNX) and always prefers
# TensorFlow when it's importable — which it always is here, since
# tensorflow is an unconditional dependency of basic-pitch itself, not
# something the [onnx] extra removes. Build the ONNX path explicitly so
# inference actually runs on onnxruntime instead of silently falling back
# to the much heavier TF SavedModel (the original source of the OOM crash).
ICASSP_2022_MODEL_PATH = build_icassp_2022_model_path(FilenameSuffix.onnx)

print(f"Basic Pitch model path: {ICASSP_2022_MODEL_PATH}")
print("Server ready ✓")

app = FastAPI(title="MusicianLearner Note Extraction API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MAX_WORKERS = 2
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Tracks concurrent in-flight /extract requests so /health can report real load.
# Only ever mutated from the async event-loop thread (increment/decrement around
# the executor call below), so no lock is needed.
in_flight = 0

MAX_FILE_SIZE  = 50 * 1024 * 1024  # 50MB — matches musician-api/config.php and the client-side check
MAX_NOTES      = 500               # hard cap — protects Firestore doc size + client rendering
DEDUP_WINDOW_S = 0.05              # merge same-pitch notes whose onsets fall within 50ms

def _transcribe(tmp_path: str):
    _, _, note_events = predict(
        tmp_path,
        ICASSP_2022_MODEL_PATH,
        onset_threshold=0.6,        # higher = fewer false-positive note starts
        frame_threshold=0.4,        # higher = only keep sustained notes
        minimum_note_length=80,     # drop anything shorter than 80 ms
    )

    # NOTE: note_events' shape depends on the backend. TensorFlow's predict()
    # returns a pandas DataFrame (supports .iterrows()); ONNX's returns a plain
    # list of tuples (onset, offset, midi_pitch, amplitude[, ...]). Since we
    # deliberately force the ONNX backend above, handle both shapes so this
    # doesn't silently break again if the backend ever changes.
    parsed = []
    if hasattr(note_events, "iterrows"):
        for _, row in note_events.iterrows():
            midi  = int(row["pitch_midi"])
            onset = float(row["start_time_s"])
            dur   = float(row["end_time_s"]) - onset
            conf  = float(row.get("velocity", 64)) / 127.0
            parsed.append((midi, onset, dur, conf))
    else:
        for event in note_events:
            midi  = int(event[2])
            onset = float(event[0])
            dur   = float(event[1]) - onset
            conf  = float(event[3]) if len(event) > 3 else 0.5  # ONNX amplitude is already 0-1
            parsed.append((midi, onset, dur, conf))

    raw_notes = [
        {
            "frequency":  round(440.0 * (2.0 ** ((midi - 69) / 12.0)), 4),
            "onset":      round(onset, 4),
            "duration":   round(max(dur, 0.05), 4),
            "confidence": round(min(conf, 1.0), 4),
            "midiNote":   midi,
        }
        for midi, onset, dur, conf in parsed
    ]

    # Deduplicate near-identical notes: same pitch, onset within DEDUP_WINDOW_S —
    # keep whichever has higher confidence. Dense/long recordings can otherwise
    # produce thousands of near-duplicate frame-level detections.
    raw_notes.sort(key=lambda n: n["onset"])
    deduped = []
    for n in raw_notes:
        if (deduped and deduped[-1]["midiNote"] == n["midiNote"]
                and (n["onset"] - deduped[-1]["onset"]) < DEDUP_WINDOW_S):
            if n["confidence"] > deduped[-1]["confidence"]:
                deduped[-1] = n
            continue
        deduped.append(n)

    # Hard cap — keep the highest-confidence notes, restore chronological order
    if len(deduped) > MAX_NOTES:
        deduped.sort(key=lambda n: n["confidence"], reverse=True)
        deduped = deduped[:MAX_NOTES]
        deduped.sort(key=lambda n: n["onset"])

    duration = max((n["onset"] + n["duration"]) for n in deduped) if deduped else 0.0
    return deduped, round(duration, 3)


@app.get("/health")
def health():
    # "idle" = at least one worker free right now; "busy" = all workers occupied.
    # The client uses this to pick which server to route a request to.
    status = "busy" if in_flight >= MAX_WORKERS else "idle"
    return {"status": status, "inFlight": in_flight, "maxWorkers": MAX_WORKERS}


@app.post("/extract")
async def extract_notes(file: UploadFile):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)",
        )

    suffix = os.path.splitext(file.filename or "audio.wav")[1].lower()
    if suffix not in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}:
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    del contents  # free the in-memory copy before the memory-heavy inference step

    global in_flight
    in_flight += 1
    try:
        loop = asyncio.get_event_loop()
        notes, duration = await loop.run_in_executor(executor, _transcribe, tmp_path)
    except Exception:
        tb = traceback.format_exc()
        print(f"[ERROR]\n{tb}")  # full traceback stays in server logs for debugging
        raise HTTPException(
            status_code=422,
            detail="Couldn't process this audio file. It may be corrupted or in an unsupported format — try a different recording, or use On-Device extraction.",
        )
    finally:
        in_flight -= 1
        try: os.unlink(tmp_path)
        except OSError: pass

    if not notes:
        raise HTTPException(status_code=422, detail="No notes detected.")

    return {"notes": notes, "durationSeconds": duration, "total": len(notes)}
