import os, tempfile, traceback, asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Basic Pitch auto-selects ONNX backend when onnxruntime is installed
# No manual model loading needed — just import the path constant
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

print(f"Basic Pitch model path: {ICASSP_2022_MODEL_PATH}")
print("Server ready ✓")

app = FastAPI(title="MusicianLearner Note Extraction API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
executor = ThreadPoolExecutor(max_workers=2)


def _transcribe(tmp_path: str):
    # predict() uses ONNX automatically when onnxruntime is installed
    _, _, note_events = predict(tmp_path, ICASSP_2022_MODEL_PATH)
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
    return {"status": "ok", "engine": "onnx"}


@app.post("/extract")
async def extract_notes(file: UploadFile):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        loop = asyncio.get_event_loop()
        notes, duration = await loop.run_in_executor(executor, _transcribe, tmp_path)
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
