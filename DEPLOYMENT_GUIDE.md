# RunPod Serverless Deployment Guide - SoulX code_102

Goal: turn SoulX-Podcast into an API endpoint that Codex can call automatically.

## What We Already Proved

Manual RunPod Pod test passed:

- GPU: A40 48GB
- Model: Soul-AILab/SoulX-Podcast-1.7B
- Output: doodle_mina.wav
- Required fix: torchvision must match torch cu126 (`torchvision==0.22.1+cu126`)

## Files In This Folder

- `handler.py`: RunPod Serverless handler.
- `Dockerfile`: builds an image with SoulX, dependencies, model, and handler.
- `download_model.py`: downloads SoulX-Podcast-1.7B at image build time.
- `test_input.json`: small Doodle request body.

## Important Cost Setting

When creating endpoint:

- Min workers: 0
- Max workers: 1 for first test
- Idle timeout: short, for example 5 minutes
- GPU: A40 48GB preferred

This keeps the endpoint from running all day.

## Build Path

### Option A: Docker Hub / GHCR

1. Build image from this folder.
2. Push image to a registry.
3. Create RunPod Serverless Template from image.
4. Create RunPod Serverless Endpoint from template.

### Option B: RunPod GitHub integration

If RunPod offers build-from-GitHub in your UI:

1. Put this folder in a GitHub repo.
2. Point RunPod template to the repo / Dockerfile.
3. Build template.

## RunPod UI Steps

1. Open RunPod Console.
2. Go to `Serverless`.
3. Create Template.
4. Use custom Docker image or GitHub Dockerfile.
5. Confirm command is:

```bash
python -u /workspace/handler.py
```

6. Create Endpoint from that template.
7. GPU: A40.
8. Set min workers 0, max workers 1.
9. Save endpoint.
10. Copy endpoint id.

## Codex Local Env

After endpoint exists, set local env:

```powershell
$env:RUNPOD_API_KEY="your_runpod_api_key"
$env:SOULX_RUNPOD_ENDPOINT_ID="your_endpoint_id"
```

Then a `doodle.voice.generate` job will call:

```text
https://api.runpod.ai/v2/{endpoint_id}/run
```

and poll:

```text
https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}
```

## Test from Local Codex

```powershell
python C:\Users\user\Desktop\codex\codes\code_102\tools\soulx_voice.py run --payload-json C:\Users\user\Desktop\gimini\soulx_doodle_test\code_102_sample_payload.json
```

If env vars are set, it calls RunPod. If not, it writes a manual packet.
