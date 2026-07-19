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

# Piano MIDI range
MIDI_MIN = 21   # A0
MIDI_MAX = 108  # C8
MAX_NOTES = 500
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB — matches musician-api/config.php and the client-side check


def _transcribe(tmp_path: str):
    _, _, note_events = predict(
        tmp_path,
        ICASSP_2022_MODEL_PATH,
        onset_threshold=0.6,        # higher = fewer false-positive note starts
        frame_threshold=0.4,        # higher = only keep sustained notes
        minimum_note_length=80,     # drop anything shorter than 80 ms
        minimum_frequency=27.5,     # A0 (lowest piano key)
        maximum_frequency=4186.0,   # C8 (highest piano key)
    )

    raw = []

    if hasattr(note_events, "iterrows"):
        for _, row in note_events.iterrows():
            raw.append((
                float(row["start_time_s"]),
                float(row["end_time_s"]),
                int(row["pitch_midi"]),
                float(row.get("velocity", 64)),
            ))
    else:
        for event in note_events:
            raw.append((
                float(event[0]),
                float(event[1]),
                int(event[2]),
                float(event[3]) * 127 if len(event) > 3 else 64.0,
            ))

    # ── Post-process: remove very short notes, clamp to piano range ──────────
    MIN_DURATION = 0.08  # 80 ms
    filtered = [
        e for e in raw
        if (e[1] - e[0]) >= MIN_DURATION
        and MIDI_MIN <= e[2] <= MIDI_MAX
    ]

    # Sort by onset then keep only the loudest note per 50ms window (dedup)
    filtered.sort(key=lambda e: e[0])
    deduped = []
    last_onset = -1.0
    last_midi  = -1
    for e in filtered:
        onset, _, midi, vel = e
        if onset - last_onset < 0.05 and midi == last_midi:
            continue  # skip near-duplicate
        deduped.append(e)
        last_onset = onset
        last_midi  = midi

    # Cap total notes
    final = deduped[:MAX_NOTES]

    notes = []
    for onset, end, midi, velocity in final:
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        notes.append({
            "frequency":  round(freq, 4),
            "onset":      round(onset, 4),
            "duration":   round(max(end - onset, 0.05), 4),
            "confidence": round(min(velocity / 127.0, 1.0), 4),
            "midiNote":   midi,
        })

    total = max((n["onset"] + n["duration"]) for n in notes) if notes else 0.0
    return notes, round(total, 3)


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
        print(f"[ERROR]\n{tb}")  # full traceback stays in Railway's own logs for debugging
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
