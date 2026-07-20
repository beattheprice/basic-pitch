# Oracle Cloud "Always Free" — considered, not used

Came up repeatedly in July 2026 research as the most resource-generous
free option (ARM VM, up to 4 vCPU/24GB RAM). Not adopted because:

- Raw VM, not push-to-deploy — you'd manage Docker, HTTPS, and restarts
  yourself, unlike Render/Cloud Run.
- The free allocation is currently being quietly cut (4 OCPU/24GB → 2
  OCPU/12GB for free-tier-only accounts), inconsistently enforced.
- Known "Out of Capacity" errors provisioning the free ARM instance.

Worth revisiting only if Cloud Run + Render + Railway stop being enough.
