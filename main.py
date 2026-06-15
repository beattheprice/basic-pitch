import os, tempfile, traceback, asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── Load madmom processors once at startup (numpy-only, no TensorFlow) ────────
print("Loading madmom piano transcription model…")
from madmom.features.notes import (
    RNNPianoNoteProcessor,
    NotePeakPickingProcessor,
)
NOTE_PROC   = RNNPianoNoteProcessor()
NOTE_PICKER = NotePeakPickingProcessor(threshold=0.35, fps=100)
print("Model ready ✓")

app = FastAPI(title="MusicianLearner Note Extraction API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
executor = ThreadPoolExecutor(max_workers=2)


def _transcribe(tmp_path: str):
    # activations → (time, pitch) activity matrix
    activations = NOTE_PROC(tmp_path)
    # peak picking → array of [onset_s, midi_note, duration_s]
    raw_notes   = NOTE_PICKER(activations)

    notes = []
    for row in raw_notes:
        onset    = float(row[0])
        midi     = int(row[1])
        duration = float(row[2]) if len(row) > 2 else 0.25
        freq     = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        notes.append({
            "frequency":  round(freq, 4),
            "onset":      round(onset, 4),
            "duration":   round(max(duration, 0.05), 4),
            "confidence": 0.9,
            "midiNote":   midi,
        })

    total = max((n["onset"] + n["duration"]) for n in notes) if notes else 0.0
    return notes, round(total, 3)


@app.get("/health")
def health():
    return {"status": "ok", "engine": "madmom"}


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
