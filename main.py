import os
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── Load model once at startup (not per-request) ──────────────────────────────
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

print("Loading Basic Pitch model…")
MODEL_PATH = ICASSP_2022_MODEL_PATH
print("Model ready.")

app = FastAPI(title="MusicianLearner Note Extraction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for CPU-bound prediction (keeps async event loop free)
executor = ThreadPoolExecutor(max_workers=2)


def run_prediction(tmp_path: str):
    """Runs Basic Pitch in a worker thread."""
    _, _, note_events = predict(tmp_path, MODEL_PATH)
    notes = []
    for _, row in note_events.iterrows():
        midi     = int(row["pitch_midi"])
        freq     = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        onset    = float(row["start_time_s"])
        duration = float(row["end_time_s"]) - onset
        velocity = float(row["velocity"]) if "velocity" in row.index else 64.0
        conf     = min(velocity / 127.0, 1.0)
        notes.append({
            "frequency":  round(freq,     4),
            "onset":      round(onset,    4),
            "duration":   round(max(duration, 0.05), 4),
            "confidence": round(conf,     4),
            "midiNote":   midi,
        })
    duration_total = max(
        (n["onset"] + n["duration"]) for n in notes
    ) if notes else 0.0
    return notes, round(duration_total, 3)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract_notes(file: UploadFile):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"

    # Write upload to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        notes, duration = await loop.run_in_executor(
            executor, run_prediction, tmp_path
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[ERROR] Prediction failed:\n{tb}")
        raise HTTPException(status_code=500, detail=tb)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not notes:
        raise HTTPException(status_code=422, detail="No notes detected in audio.")

    return {"notes": notes, "durationSeconds": duration}
