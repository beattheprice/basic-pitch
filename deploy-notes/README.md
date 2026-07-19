# Multi-provider deploy notes

Same `Dockerfile` + `main.py` + `requirements.txt` deploys to all four —
no code differences between providers, only the deploy mechanism differs.

| Provider | File | Free RAM | Sleeps? | Card required? |
|---|---|---|---|---|
| Cloud Run | `cloud-run.md` | up to 32GB (configurable) | scales to zero | yes |
| Hugging Face Spaces | `huggingface-spaces.md` | ~16GB | after ~48h idle | no |
| Render | `render.md` | 512MB | after ~15min idle | no |
| Koyeb | `koyeb.md` | tight (Eco tier) | scales to zero | no |

Deploy in whatever order suits you — each is independent. After each one
is live, run its `curl .../health` check before adding it to `servers.php`.

Once at least two are confirmed working, update
`ycreative.me/musician-api/servers.php` with their URLs — that's the single
place the apps read the server list from, so nothing else needs to change
per provider going forward.
