# Hugging Face Spaces (Docker SDK)

> **UPDATE (checked live): no longer free.** As of 2026, Docker/Gradio
> Spaces on compute require a PRO subscription ($9/mo) — only Static
> Spaces (no server code) remain free. Not viable for this use case
> without paying. Left here for reference only; not in servers.php.

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
