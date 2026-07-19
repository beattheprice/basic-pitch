# Google Cloud Run

1. Install the CLI if you don't have it: `brew install --cask google-cloud-sdk`
2. `gcloud auth login` (opens browser — you do this step)
3. `gcloud config set project YOUR_PROJECT_ID` (create a project in the
   Cloud Console first if you don't have one — no charge unless you exceed
   the free tier)
4. From this directory:
   ```
   gcloud run deploy musicianlearner-basic-pitch \
     --source . \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 4Gi \
     --cpu 2 \
     --min-instances 0 \
     --max-instances 3 \
     --timeout 300
   ```
5. gcloud builds the Dockerfile via Cloud Build and deploys automatically —
   no separate build step needed.
6. Note the returned `*.run.app` URL for `servers.php`.

**Why --memory 4Gi**: gives real headroom over Render/Koyeb's free tiers for
ONNX inference on larger files — this is the safety-margin option.

**Test once live**:
```
curl https://YOUR-SERVICE.run.app/health
```
