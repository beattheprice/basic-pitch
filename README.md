---
title: MusicianLearner Basic Pitch
emoji: 🎵
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# basic-pitch

Note-extraction API for the MusicianLearner app — FastAPI + Basic Pitch (ONNX backend).

Deploys as-is to any Docker-compatible host: Railway, Google Cloud Run, Hugging Face
Spaces, Render, Koyeb. See `/deploy-notes/` for provider-specific setup.

- `GET /health` → `{"status": "idle"|"busy", "inFlight": N, "maxWorkers": N}`
- `POST /extract` → multipart file upload → `{"notes": [...], "durationSeconds": N, "total": N}`
