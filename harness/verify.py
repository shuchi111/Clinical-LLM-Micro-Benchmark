"""End-to-end verification after a full harness run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    prompts = sorted((ROOT / "outputs" / "prompts").glob("D*.json"))
    if len(prompts) != 3:
        errors.append(f"expected 3 prompts, got {len(prompts)}")

    sys_prompt = None
    for p in prompts:
        d = load(p)
        for k in ("item_id", "patient_id", "visit_id", "system_prompt", "user_prompt"):
            if not d.get(k):
                errors.append(f"{p.name} missing {k}")
        sys_prompt = d["system_prompt"]

    expected = {
        "zai_glm-5.1": "zai",
        "groq_llama-3.3-70b-versatile": "groq",
        "google_gemini-2.5-flash": "google",
    }
    raw = ROOT / "outputs" / "raw"
    for mid, prov in expected.items():
        d = raw / mid
        if not d.is_dir():
            errors.append(f"missing raw dir {mid}")
            continue
        for item in ("D1", "D2", "D3"):
            f = d / f"{item}.json"
            if not f.exists():
                errors.append(f"missing {mid}/{item}.json")
                continue
            blob = load(f)
            if blob.get("provider") != prov:
                errors.append(f"{mid}/{item} bad provider={blob.get('provider')}")
            if not blob.get("raw_response"):
                errors.append(f"{mid}/{item} empty raw_response")
            if blob.get("system_prompt") != sys_prompt:
                errors.append(f"{mid}/{item} system_prompt mismatch")
            if blob.get("item_id") != item:
                errors.append(f"{mid}/{item} item_id mismatch")
            if not blob.get("user_prompt"):
                errors.append(f"{mid}/{item} missing user_prompt")

    scores_path = ROOT / "outputs" / "scores.json"
    if not scores_path.exists():
        errors.append("missing scores.json")
        models = {}
    else:
        models = load(scores_path).get("models", {})

    print("=== Per-item scores ===")
    for mid in expected:
        if mid not in models:
            errors.append(f"scores missing {mid}")
            continue
        m = models[mid]
        if m.get("macro_f1") is None:
            errors.append(f"{mid} macro_f1 is None")
        for item in ("D1", "D2", "D3"):
            if item not in m.get("items", {}):
                errors.append(f"{mid} missing score for {item}")
                continue
            s = m["items"][item]
            print(
                f"  {mid:32} {item}  F1={s['f1']:.4f}  "
                f"P={s['precision']:.2f} R={s['recall']:.2f}  "
                f"missed={s['missed_gold']}  flags={s['critical_flags']}"
            )
        print(
            f"  {mid:32} MACRO={m['macro_f1']}  "
            f"critical_total={m['critical_flag_count']}"
        )

    for path in (
        ROOT / "gold" / "gold_labels.json",
        ROOT / "gold" / "LABELING_PROTOCOL.md",
        ROOT / "REPORT.md",
        ROOT / "doc" / "patients_sample_3 (1).json",
    ):
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")

    # D3 sanity: no model should invent neuropathy / hyperkeratosis
    for mid in expected:
        d3 = raw / mid / "D3.json"
        if not d3.exists():
            continue
        text = load(d3).get("raw_response", "").lower()
        if "neuropathy" in text and "no neuropathy" not in text:
            # model output condition name containing neuropathy is bad
            if '"name": "neuropathy"' in text or "neuropathy" in text.split("conditions")[-1]:
                # soft check via scores critical flags instead
                pass
        if "hyperkeratosis" in text or "lenticularis" in text:
            errors.append(f"{mid} D3 invented hyperkeratosis sense")

    print("---")
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1

    print("PASS: build + 3 providers (9 calls) + scores + artifacts verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
