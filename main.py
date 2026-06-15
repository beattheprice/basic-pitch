import os, tempfile, traceback, asyncio, numpy as np
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── Load and WARM UP the model at startup ─────────────────────────────────────
print("Importing Basic Pitch…")
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import tensorflow as tf

print("Loading TF model…")
_MODEL = tf.saved_model.load(str(ICASSP_2022_MODEL_PATH))

# Warm-up: run a silent 1-second buffer so the first real request is fast
print("Warming up model…")
_SILENCE = np.zeros(22050, dtype=np.float32)
_SILENCE_PATH = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
import soundfile as sf
sf.write(_SILENCE_PATH.name, _SILENCE, 22050)
predict(_SILENCE_PATH.name, _MODEL)
os.unlink(_SILENCE_PATH.name)
print("Model ready ✓")

# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="MusicianLearner Note Extraction API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
executor = ThreadPoolExecutor(max_workers=1)


def _predict(tmp_path: str):
    _, _, note_events = predict(tmp_path, _MODEL)
    notes = []
    for _, row in note_events.iterrows():
        midi     = int(row["pitch_midi"])
        freq     = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        onset    = float(row["start_time_s"])
        duration = float(row["end_time_s"]) - onset
        velocity = float(row.get("velocity", 64))
        notes.append({
            "frequency":  round(freq, 4),
            "onset":      round(onset, 4),
            "duration":   round(max(duration, 0.05), 4),
            "confidence": round(min(velocity / 127.0, 1.0), 4),
            "midiNote":   midi,
        })
    total = max((n["onset"] + n["duration"]) for n in notes) if notes else 0.0
    return notes, round(total, 3)


@app.get("/health")
def health():
    return {"status": "ok", "model": "loaded"}


@app.post("/extract")
async def extract_notes(file: UploadFile):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        loop   = asyncio.get_event_loop()
        notes, duration = await loop.run_in_executor(executor, _predict, tmp_path)
    except Exception:
        tb = traceback.format_exc()
        print(f"[ERROR]\n{tb}")
        raise HTTPException(status_code=500, detail=tb)
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass
    if not notes:
        raise HTTPException(status_code=422, detail="No notes detected.")
    return {"notes": notes, "durationSeconds": duration}
