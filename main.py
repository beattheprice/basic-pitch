from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os, math

app = FastAPI(title="MusicianLearner Note Extraction API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract_notes(file: UploadFile):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        _, _, note_events = predict(tmp_path, ICASSP_2022_MODEL_PATH)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")
    finally:
        os.unlink(tmp_path)

    notes = []
    for _, row in note_events.iterrows():
        midi   = int(row["pitch_midi"])
        freq   = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        onset  = float(row["start_time_s"])
        dur    = float(row["end_time_s"]) - onset
        conf   = float(row.get("velocity", 64)) / 127.0
        notes.append({
            "frequency": round(freq, 4),
            "onset":     round(onset, 4),
            "duration":  round(max(dur, 0.05), 4),
            "confidence": round(min(conf, 1.0), 4),
            "midiNote":  midi
        })

    duration = max((n["onset"] + n["duration"]) for n in notes) if notes else 0.0
    return {"notes": notes, "durationSeconds": round(duration, 3)}
