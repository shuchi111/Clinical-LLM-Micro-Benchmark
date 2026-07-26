"""Paths, prompts, and .env - the boring but important bits."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GOLD_PATH = ROOT / "gold" / "gold_labels.json"
PROMPT_DIR = ROOT / "outputs" / "prompts"
RAW_DIR = ROOT / "outputs" / "raw"
SCORES_PATH = ROOT / "outputs" / "scores.json"

# Patient JSON is local-only (gitignored under doc/).
DATA_CANDIDATES = [
    ROOT / "doc" / "patients_sample_3 (1).json",
    ROOT / "patients_sample_3 (1).json",
    ROOT / "data" / "patients_sample_3.json",
]

SYSTEM_PROMPT = """\
You are a clinical information extraction assistant.
Extract diagnoses/conditions that are AFFIRMATIVELY present from the raw_diagnosis token list.
Rules:
- Expand common clinical abbreviations to clear English labels.
- Do NOT invent conditions that are not supported by the tokens.
- Ignore duration-only fragments (e.g. "24 years").
- Honor negation: tokens like "no X" mean X is NOT present.
- Output JSON only, with this schema:
{"conditions":[{"name":"<label>","evidence_token":"<exact token from input>"}]}
- Deduplicate. No prose outside JSON."""

USER_TEMPLATE = """\
Patient ID: {patient_id}
Visit ID: {visit_id}

raw_diagnosis tokens:
{raw_json}

Extract affirmative conditions as JSON."""


def load_dotenv(path: Path | None = None) -> Path | None:
    """Load KEY=VALUE pairs from .env without clobbering real env vars."""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value
    return env_path


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise SystemExit(f"Missing {name}. Put it in .env (never commit secrets).")
    return val
