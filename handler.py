import base64
import json
import os
import subprocess
import traceback
import uuid
from pathlib import Path

import runpod

SOULX_DIR = Path(os.getenv("SOULX_DIR", "/workspace/SoulX-Podcast"))
MODEL_PATH = os.getenv(
    "SOULX_MODEL_PATH",
    "/workspace/SoulX-Podcast/pretrained_models/SoulX-Podcast-1.7B",
)

def build_script(text):
    return {
        "speakers": {
            "S1": {
                "prompt_audio": "example/audios/female_mandarin.wav",
                "prompt_text": "喜歡分享故事、聲音溫柔自然，像媽媽陪孩子說晚安故事。",
            },
            "S2": {
                "prompt_audio": "example/audios/male_mandarin.wav",
                "prompt_text": "不用怕，我會陪著你。勇敢不是都不害怕，而是害怕的時候，還願意慢慢往前走。",
            },
        },
        "text": [
            ["S1", text],
        ],
    }

def handler(job):
    try:
        data = job.get("input", {})
        text = data.get("text") or "你好，這是 SoulX 真實語音生成測試。"

        job_id = str(uuid.uuid4())
        work_dir = Path("/tmp/soulx_jobs") / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        script_path = work_dir / "script.json"
        output_path = work_dir / "result.wav"

        script = data.get("script") or build_script(text)
        script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SOULX_DIR)

        cmd = [
            "python",
            "cli/podcast.py",
            "--json_path",
            str(script_path),
            "--model_path",
            MODEL_PATH,
            "--output_path",
            str(output_path),
            "--seed",
            str(data.get("seed", 11)),
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(SOULX_DIR),
            env=env,
            text=True,
            capture_output=True,
            timeout=int(data.get("timeout", 600)),
        )

        if proc.returncode != 0:
            return {
                "ok": False,
                "stage": "soulx_inference_failed",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            }

        audio = output_path.read_bytes()

        return {
            "ok": True,
            "message": "SoulX wav generated",
            "filename": "result.wav",
            "content_type": "audio/wav",
            "bytes": len(audio),
            "audio_b64": base64.b64encode(audio).decode("ascii"),
            "stdout": proc.stdout[-2000:],
        }

    except Exception:
        return {
            "ok": False,
            "stage": "handler_exception",
            "error": traceback.format_exc(),
        }

runpod.serverless.start({"handler": handler})
