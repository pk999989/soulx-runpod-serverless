import base64
import json
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import runpod


ROOT = Path(os.environ.get("SOULX_ROOT", "/workspace/soulx_test/SoulX-Podcast"))
MODEL_PATH = Path(os.environ.get("SOULX_MODEL_PATH", ROOT / "pretrained_models/SoulX-Podcast-1.7B"))
OUTPUT_DIR = Path(os.environ.get("SOULX_OUTPUT_DIR", "/tmp/soulx_outputs"))
MAX_CHARS_PER_SEGMENT = int(os.environ.get("SOULX_MAX_CHARS_PER_SEGMENT", "90"))


def _split_zh_text(text, max_chars=MAX_CHARS_PER_SEGMENT):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    raw_parts = re.split(r"(?<=[。！？!?；;])", text)
    chunks = []
    current = ""
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) <= max_chars:
            current += part
        else:
            if current:
                chunks.append(current)
            while len(part) > max_chars:
                chunks.append(part[:max_chars])
                part = part[max_chars:]
            current = part
    if current:
        chunks.append(current)
    return chunks


def _build_script(payload):
    if isinstance(payload.get("script"), dict):
        return payload["script"]

    text = payload.get("text") or payload.get("prompt") or payload.get("narration") or ""
    dialogue = payload.get("dialogue")
    if dialogue and isinstance(dialogue, list):
        lines = []
        for item in dialogue:
            speaker = item.get("speaker", "S1") if isinstance(item, dict) else "S1"
            line = item.get("text", "") if isinstance(item, dict) else str(item)
            if line.strip():
                lines.append([speaker, line.strip()])
    else:
        chunks = _split_zh_text(text)
        lines = [["S1", chunk] for chunk in chunks]

    if not lines:
        raise ValueError("No text/script/dialogue found in input.")

    return {
        "speakers": {
            "S1": {
                "prompt_audio": str(ROOT / "example/audios/female_mandarin.wav"),
                "prompt_text": "溫柔、清楚、像台灣媽媽說故事一樣，語氣自然，有停頓，也有鼓勵孩子的感覺。"
            },
            "S2": {
                "prompt_audio": str(ROOT / "example/audios/male_mandarin.wav"),
                "prompt_text": "不用怕，我會陪著你。勇敢不是都不害怕，而是害怕的時候，還願意慢慢往前走。"
            }
        },
        "text": lines
    }


def _wav_duration(path):
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())


def handler(job):
    payload = job.get("input") or {}
    seed = int(payload.get("seed", 7))
    request_id = job.get("id") or "manual"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    script = _build_script(payload)
    input_chars = sum(len(line[1]) for line in script["text"])

    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "script.json"
        out_path = OUTPUT_DIR / f"{request_id}.wav"
        script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)

        
        cmd = [
            "python",
            str(ROOT / "cli/podcast.py"),
            "--json_path",
            str(script_path),
            "--model_path",
            str(MODEL_PATH),
            "--output_path",
            str(out_path),
            "--seed",
            str(seed),
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout_seconds", 600)),
        )

        if completed.returncode != 0:
            return {
                "ok": False,
                "error": "SoulX inference failed",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "segments_count": len(script["text"]),
                "input_chars": input_chars,
            }

    duration = _wav_duration(out_path)
    wav_bytes = out_path.read_bytes()
    min_expected = max(3.0, min(90.0, input_chars / 9.0))
    warning = None
    if duration < min_expected:
        warning = f"audio_too_short: duration={duration:.2f}s expected_at_least={min_expected:.2f}s"

    return {
        "ok": warning is None,
        "warning": warning,
        "message": "SoulX wav generated",
        "filename": "result.wav",
        "content_type": "audio/wav",
        "duration_seconds": round(duration, 2),
        "bytes": len(wav_bytes),
        "input_chars": input_chars,
        "segments_count": len(script["text"]),
        "script_preview": script["text"][:3],
        "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
    }


runpod.serverless.start({"handler": handler})


















































