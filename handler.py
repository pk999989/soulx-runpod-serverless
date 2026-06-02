import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import runpod


HANDLER_VERSION = "soulx-full-v3-path-detect-20260602"
OUTPUT_DIR = Path(os.environ.get("SOULX_OUTPUT_DIR", "/tmp/soulx_outputs"))
MAX_CHARS_PER_SEGMENT = int(os.environ.get("SOULX_MAX_CHARS_PER_SEGMENT", "90"))

ROOT_CANDIDATES = [
    os.environ.get("SOULX_ROOT"),
    "/workspace/SoulX-Podcast",
    "/workspace/soulx_test/SoulX-Podcast",
    "/app/SoulX-Podcast",
    "/workspace",
    "/app",
]


def _resolve_root():
    checked = []
    for item in ROOT_CANDIDATES:
        if not item:
            continue
        root = Path(item)
        checked.append(str(root))
        if (root / "cli/podcast.py").exists() and (root / "soulxpodcast").exists():
            return root, checked

    for base in [Path("/workspace"), Path("/app")]:
        if not base.exists():
            continue
        for found in base.rglob("cli/podcast.py"):
            root = found.parent.parent
            checked.append(str(root))
            if (root / "soulxpodcast").exists():
                return root, checked

    raise FileNotFoundError(
        "Cannot find SoulX-Podcast root. Checked: " + ", ".join(checked)
    )


def _resolve_model(root):
    candidates = [
        os.environ.get("SOULX_MODEL_PATH"),
        root / "pretrained_models/SoulX-Podcast-1.7B",
        root / "SoulX-Podcast-1.7B",
        "/runpod-volume/pretrained_models/SoulX-Podcast-1.7B",
        "/workspace/pretrained_models/SoulX-Podcast-1.7B",
    ]
    checked = []
    for item in candidates:
        if not item:
            continue
        model_path = Path(item)
        checked.append(str(model_path))
        if model_path.exists():
            return model_path, checked

    raise FileNotFoundError(
        "Cannot find SoulX model path. Checked: " + ", ".join(checked)
    )


def _split_text(text, max_chars=MAX_CHARS_PER_SEGMENT):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    parts = re.split(r"(?<=[.!?;。！？；])", text)
    chunks = []
    current = ""
    for part in parts:
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


def _build_script(payload, root):
    if isinstance(payload.get("script"), dict):
        return payload["script"]

    dialogue = payload.get("dialogue")
    if dialogue and isinstance(dialogue, list):
        lines = []
        for item in dialogue:
            if isinstance(item, dict):
                speaker = item.get("speaker", "S1")
                line = item.get("text", "")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                speaker = item[0]
                line = item[1]
            else:
                speaker = "S1"
                line = str(item)
            if str(line).strip():
                lines.append([str(speaker), str(line).strip()])
    else:
        text = payload.get("text") or payload.get("prompt") or payload.get("narration") or ""
        lines = [["S1", chunk] for chunk in _split_text(text)]

    if not lines:
        raise ValueError("No text/script/dialogue found in input.")

    return {
        "speakers": {
            "S1": {
                "prompt_audio": str(root / "example/audios/female_mandarin.wav"),
                "prompt_text": (
                    "A warm Mandarin storyteller voice. Natural, clear, gentle, "
                    "with pauses and encouraging emotion."
                ),
            },
            "S2": {
                "prompt_audio": str(root / "example/audios/male_mandarin.wav"),
                "prompt_text": (
                    "A calm Mandarin co-host voice. Friendly, steady, and supportive."
                ),
            },
        },
        "text": lines,
    }


def _wav_duration(path):
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())


def _dir_listing(path):
    base = Path(path)
    if not base.exists():
        return []
    return [p.name for p in base.iterdir()][:80]


def handler(job):
    payload = job.get("input") or {}
    seed = int(payload.get("seed", 7))
    request_id = job.get("id") or "manual"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        root, root_checked = _resolve_root()
        model_path, model_checked = _resolve_model(root)
        script = _build_script(payload, root)
    except Exception as exc:
        return {
            "handler_version": HANDLER_VERSION,
            "ok": False,
            "error": str(exc),
            "cwd": os.getcwd(),
            "python": shutil.which("python"),
            "workspace_listing": _dir_listing("/workspace"),
            "app_listing": _dir_listing("/app"),
        }

    input_chars = sum(len(line[1]) for line in script["text"])

    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "script.json"
        out_path = OUTPUT_DIR / f"{request_id}.wav"
        script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)

        cmd = [
            "python",
            str(root / "cli/podcast.py"),
            "--json_path",
            str(script_path),
            "--model_path",
            str(model_path),
            "--output_path",
            str(out_path),
            "--seed",
            str(seed),
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout_seconds", 600)),
        )

        if completed.returncode != 0:
            return {
                "handler_version": HANDLER_VERSION,
                "ok": False,
                "error": "SoulX inference failed",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "segments_count": len(script["text"]),
                "input_chars": input_chars,
                "soulx_root": str(root),
                "model_path": str(model_path),
            }

    duration = _wav_duration(out_path)
    wav_bytes = out_path.read_bytes()
    min_expected = max(3.0, min(90.0, input_chars / 9.0))
    warning = None
    if duration < min_expected:
        warning = f"audio_too_short: duration={duration:.2f}s expected_at_least={min_expected:.2f}s"

    return {
        "handler_version": HANDLER_VERSION,
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
        "soulx_root": str(root),
        "model_path": str(model_path),
        "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
    }


runpod.serverless.start({"handler": handler})



















































