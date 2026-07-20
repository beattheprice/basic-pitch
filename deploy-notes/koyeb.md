# Koyeb

> **UPDATE (checked live, Jul 2026): no longer viable.** Koyeb was
> acquired by Mistral AI (Feb 2026). New signups can only choose Pro plan
> and above — the free Starter tier is closed to new accounts. Existing
> accounts are unaffected, but that doesn't help a fresh deploy. Not in
> servers.php. Revisit only if this policy changes.

**Easiest path — dashboard, no CLI needed:**
1. Free account at koyeb.com (GitHub login works).
2. Create Service → GitHub → select `beattheprice/basic-pitch` →
   Koyeb auto-detects the Dockerfile.
3. Instance: **Free (Eco)**. Port: match the Dockerfile's `PORT` env
   (Koyeb injects its own `PORT` value automatically — the Dockerfile's
   `${PORT}` picks it up, so no manual port edit needed).
4. Health check path: `/health`.
5. Deploy. Koyeb gives you a URL like:
   `https://musicianlearner-basic-pitch-YOUR_ORG.koyeb.app`

**CLI alternative** (if you'd rather script it):
```
brew install koyeb/tap/koyeb
koyeb login
koyeb deploy --archive . --config koyeb.yaml
```

**Test once live**:
```
curl https://YOUR-SERVICE.koyeb.app/health
```
