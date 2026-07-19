# Hugging Face Spaces (Docker SDK)

1. Create a free account at huggingface.co if you don't have one.
2. In the browser: New → Space → name it (e.g. `musicianlearner-basic-pitch`)
   → SDK: **Docker** → Hardware: **CPU basic (free)** → Create Space.
3. HF gives you a git remote URL like:
   `https://huggingface.co/spaces/YOUR_USERNAME/musicianlearner-basic-pitch`
4. From this `.basic-pitch-deploy` directory:
   ```
   git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/musicianlearner-basic-pitch
   git push hf main
   ```
   (You'll be prompted for HF credentials — use a HF access token as the
   password, generated from Settings → Access Tokens.)
5. The `README.md` frontmatter (`sdk: docker`, `app_port: 7860`) is already
   in place — HF Spaces reads it automatically, no dashboard config needed.
6. Space builds automatically on push. Your URL will be:
   `https://YOUR_USERNAME-musicianlearner-basic-pitch.hf.space`

**Note**: free CPU Spaces sleep after ~48h of inactivity and cold-start on
wake (not just short idle-timeout sleep like Render) — factor this into
health-check timeout tuning on the client.

**Test once live**:
```
curl https://YOUR_USERNAME-musicianlearner-basic-pitch.hf.space/health
```
