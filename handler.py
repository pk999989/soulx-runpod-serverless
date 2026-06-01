#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RunPod Serverless handler for SoulX-Podcast.

This is a deployment template. Build a RunPod worker image with SoulX-Podcast
and its model preinstalled, then use this as the endpoint command.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import runpod

SOULX_DIR = Path(os.environ.get("SOULX_DIR", "/workspace/SoulX-Podcast"))
MODEL_PATH = Path(os.environ.get("SOULX_MODEL_PATH", str(SOULX_DIR / "pretrained_models" / "SoulX-Podcast-1.7B")))


def safe_name(value: Any, fallback: str = "soulx") -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip("-._")
    return text[:80] or fallback


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav:
            return round(wav.getnframes() / float(wav.getframerate()), 3)
    except Exception:
        return None


def handler(job: dict[str, Any]) -> dict[str, Any]:
    job_input = job.get("input") or {}
    script = job_input.get("script")
    if not isinstance(script, dict):
        return {"success": False, "error": "input.script is required"}
    if not SOULX_DIR.exists():
        return {"success": False, "error": f"SoulX dir not found: {SOULX_DIR}"}
    if not MODEL_PATH.exists():
        return {"success": False, "error": f"SoulX model not found: {MODEL_PATH}"}

    tx_id = safe_name(job_input.get("tx_id") or job.get("id") or "voice")
    seed = int(job_input.get("seed") or 11)
    with tempfile.TemporaryDirectory(prefix="soulx_") as tmp:
        tmp_dir = Path(tmp)
        input_json = tmp_dir / "script.json"
        output_wav = tmp_dir / f"{tx_id}_soulx.wav"
        input_json.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SOULX_DIR)
        cmd = [
            sys.executable,
            str(SOULX_DIR / "cli" / "podcast.py"),
            "--json_path",
            str(input_json),
            "--model_path",
            str(MODEL_PATH),
            "--output_path",
            str(output_wav),
            "--seed",
            str(seed),
        ]
        proc = subprocess.run(cmd, cwd=str(SOULX_DIR), env=env, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0 or not output_wav.exists():
            return {
                "success": False,
                "error": "SoulX inference failed",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            }
        audio_bytes = output_wav.read_bytes()
        return {
            "success": True,
            "filename": output_wav.name,
            "duration_sec": wav_duration(output_wav),
            "content_type": "audio/wav",
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
        }


runpod.serverless.start({"handler": handler})
