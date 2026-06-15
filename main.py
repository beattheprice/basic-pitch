import os, tempfile, traceback, asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

print(f"Basic Pitch model path: {ICASSP_2022_MODEL_PATH}")
print("Server ready ✓")

app = FastAPI(title="MusicianLearner Note Extraction API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
executor = ThreadPoolExecutor(max_workers=2)

# Supported audio extensions — .audio is treated as .wav
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}


def _parse_notes(note_events) -> list:
    """Handle both DataFrame and list formats that Basic Pitch may return."""
    notes = []

    if hasattr(note_events, "iterrows"):
        # DataFrame format
        for _, row in note_events.iterrows():
            midi     = int(row["pitch_midi"])
            onset    = float(row["start_time_s"])
            duration = float(row["end_time_s"]) - onset
            velocity = float(row.get("velocity", 64))
            freq     = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            notes.append({
                "frequency":  round(freq, 4),
                "onset":      round(onset, 4),
                "duration":   round(max(duration, 0.05), 4),
                "confidence": round(min(velocity / 127.0, 1.0), 4),
                "midiNote":   midi,
            })
    else:
        # List format: each item is (start_time, end_time, pitch_midi, amplitude, ...)
        for event in note_events:
            onset    = float(event[0])
            end_time = float(event[1])
            midi     = int(event[2])
            amplitude = float(event[3]) if len(event) > 3 else 0.5
            duration = end_time - onset
            freq     = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            notes.append({
                "frequency":  round(freq, 4),
                "onset":      round(onset, 4),
                "duration":   round(max(duration, 0.05), 4),
                "confidence": round(min(amplitude, 1.0), 4),
                "midiNote":   midi,
            })

    return notes


def _transcribe(tmp_path: str):
    _, _, note_events = predict(tmp_path, ICASSP_2022_MODEL_PATH)
    notes = _parse_notes(note_events)
    total = max((n["onset"] + n["duration"]) for n in notes) if notes else 0.0
    return notes, round(total, 3)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract_notes(file: UploadFile):
    filename = file.filename or "audio.wav"
    ext = os.path.splitext(filename)[1].lower()

    # Treat unknown/missing extension as wav (covers Android's .audio)
    if ext not in AUDIO_EXTS:
        ext = ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
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
