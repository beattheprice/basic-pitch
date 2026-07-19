# Render

1. Create a free account at render.com if you don't have one (GitHub login
   works, no credit card required for free tier).
2. Push this repo to GitHub if it isn't already (it should be, as
   `github.com/beattheprice/basic-pitch` per your existing Railway deploy).
3. In the Render dashboard: New → Blueprint → connect the
   `beattheprice/basic-pitch` repo → Render detects `render.yaml`
   automatically and proposes the `musicianlearner-basic-pitch` web service.
4. Click Apply. First build takes a few minutes (installs ffmpeg + onnxruntime).
5. Render assigns a URL like `https://musicianlearner-basic-pitch.onrender.com`.

**Known risk**: free tier is 512MB RAM, which is the tightest of all four
options here. If Basic Pitch OOMs on larger files (same failure mode as the
original Railway TensorFlow crash), this is the one to watch first — test
with a real full-length M4A before trusting it in the rotation.

**Also**: free services spin down after ~15 min idle, ~30s+ cold start on
wake — the client's health-check timeout needs to tolerate this.

**Test once live**:
```
curl https://YOUR-SERVICE.onrender.com/health
```
