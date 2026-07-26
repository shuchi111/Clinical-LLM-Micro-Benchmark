"""Tiny I/O helpers. Prefer curl for HTTPS on flaky Windows DNS / WAF setups."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def curl_json(url: str, headers: dict[str, str], body: dict, timeout: int = 180) -> tuple[int, dict]:
    """POST JSON via curl.exe (or curl). Returns (http_code, parsed_json)."""
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl not found on PATH")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(body, f)
        body_path = f.name

    cmd = [
        curl,
        "-sS",
        "-w",
        "\n%{http_code}",
        "--location",
        url,
        "--header",
        "Content-Type: application/json",
    ]
    for k, v in headers.items():
        cmd += ["--header", f"{k}: {v}"]
    cmd += ["--data", f"@{body_path}"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    finally:
        Path(body_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr or proc.stdout}")

    out = proc.stdout.rstrip("\n")
    if "\n" not in out:
        raise RuntimeError(f"Unexpected curl output: {out[:500]}")
    text, code_s = out.rsplit("\n", 1)
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON response (HTTP {code_s}): {text[:500]}") from e
    return int(code_s), payload
