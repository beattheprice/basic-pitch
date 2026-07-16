from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os

app = FastAPI(title="MusicianLearner Note Extraction API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_FILE_SIZE   = 50 * 1024 * 1024  # 50MB — matches musician-api/config.php
MAX_NOTES       = 500               # hard cap — protects Firestore doc size + client rendering
DEDUP_WINDOW_S  = 0.05              # merge same-pitch notes onset within 50ms of each other

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract_notes(file: UploadFile):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)",
        )

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    del contents  # free the in-memory copy before the memory-heavy inference step

    try:
        _, _, note_events = predict(
            tmp_path,
            ICASSP_2022_MODEL_PATH,
            onset_threshold=0.6,
            frame_threshold=0.4,
            minimum_note_length=80,  # ms
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")
    finally:
        os.unlink(tmp_path)

    raw_notes = []
    for _, row in note_events.iterrows():
        midi   = int(row["pitch_midi"])
        freq   = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        onset  = float(row["start_time_s"])
        dur    = float(row["end_time_s"]) - onset
        conf   = float(row.get("velocity", 64)) / 127.0
        raw_notes.append({
            "frequency":  round(freq, 4),
            "onset":      round(onset, 4),
            "duration":   round(max(dur, 0.05), 4),
            "confidence": round(min(conf, 1.0), 4),
            "midiNote":   midi,
        })

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
    return {"notes": deduped, "durationSeconds": round(duration, 3), "total": len(deduped)}
