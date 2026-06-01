# RunPod Serverless template for code_102

This folder is a starter worker for a future SoulX Serverless endpoint.

RunPod serverless workers expose a `handler(job)` function and start it with:

```python
runpod.serverless.start({"handler": handler})
```

The current template assumes the deployed image already contains:

- SoulX-Podcast repo at `/workspace/SoulX-Podcast`
- model at `/workspace/SoulX-Podcast/pretrained_models/SoulX-Podcast-1.7B`
- fixed dependency versions from our successful A40 test:
  - torch 2.7.1+cu126
  - torchvision 0.22.1+cu126
  - huggingface_hub 0.36.2

## Request input

```json
{
  "input": {
    "tx_id": "abc",
    "script": {
      "speakers": {
        "S1": {"prompt_audio": "example/audios/female_mandarin.wav", "prompt_text": "..."},
        "S2": {"prompt_audio": "example/audios/male_mandarin.wav", "prompt_text": "..."}
      },
      "text": [["S1", "..."], ["S2", "..."]]
    },
    "seed": 11,
    "format": "wav"
  }
}
```

## Response

For the first version, the worker returns base64 audio. Later we should upload the audio to Supabase Storage directly and return `audio_url`.

```json
{
  "success": true,
  "filename": "abc_soulx.wav",
  "duration_sec": 37.6,
  "audio_b64": "..."
}
```
