FROM python:3.11-slim

# ffmpeg is required to decode M4A/AAC (the default Android recording format) —
# soundfile can't handle it on its own. This is the Dockerfile equivalent of
# nixpacks.toml's nixPkgs = ["ffmpeg"] used on Railway.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Most platforms (Cloud Run, Render, Koyeb) inject $PORT at runtime.
# Hugging Face Spaces defaults to 7860 unless overridden in its README frontmatter —
# we default to 7860 here too so the same image works there without extra config.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
