"""Build prompts -> run models -> score. The actual benchmark loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.clients import Completion, LLMClient
from harness.config import (
    DATA_CANDIDATES,
    GOLD_PATH,
    PROMPT_DIR,
    RAW_DIR,
    ROOT,
    SCORES_PATH,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from harness.io_util import read_json, write_json


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@dataclass
class PromptItem:
    item_id: str
    patient_id: str
    visit_id: str
    system_prompt: str
    user_prompt: str
    raw_diagnosis: Any


class PromptBuilder:
    """Hand-built gold IDs x chart visits -> identical prompts for every model."""

    def __init__(self, gold_path: Path = GOLD_PATH, out_dir: Path = PROMPT_DIR):
        self.gold_path = gold_path
        self.out_dir = out_dir

    def _load_patients(self) -> tuple[list, Path]:
        for path in DATA_CANDIDATES:
            if path.exists():
                return read_json(path), path  # type: ignore[return-value]
        raise FileNotFoundError(
            "Patient JSON not found. Put it in doc/ (local only; do not commit)."
        )

    @staticmethod
    def _index_visits(patients: list) -> dict[tuple[str, str], dict]:
        idx: dict[tuple[str, str], dict] = {}
        for pt in patients:
            pid = pt["patient_id"]
            for visit in pt.get("visit_list") or []:
                idx[(pid, visit["visit_id"])] = visit
        return idx

    def build(self) -> list[PromptItem]:
        patients, data_path = self._load_patients()
        gold = read_json(self.gold_path)
        visits = self._index_visits(patients)  # type: ignore[arg-type]
        self.out_dir.mkdir(parents=True, exist_ok=True)

        items: list[PromptItem] = []
        manifest = {
            "data_path_used": str(data_path),
            "system_prompt": SYSTEM_PROMPT,
            "items": [],
        }

        for g in gold["items"]:  # type: ignore[index]
            visit = visits[(g["patient_id"], g["visit_id"])]
            raw = visit.get("raw_diagnosis")
            user = USER_TEMPLATE.format(
                patient_id=g["patient_id"],
                visit_id=g["visit_id"],
                raw_json=json.dumps(raw, ensure_ascii=False, indent=2),
            )
            item = PromptItem(
                item_id=g["item_id"],
                patient_id=g["patient_id"],
                visit_id=g["visit_id"],
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user,
                raw_diagnosis=raw,
            )
            out = self.out_dir / f"{item.item_id}_{item.patient_id}_{item.visit_id}.json"
            write_json(
                out,
                {
                    "item_id": item.item_id,
                    "patient_id": item.patient_id,
                    "visit_id": item.visit_id,
                    "system_prompt": item.system_prompt,
                    "user_prompt": item.user_prompt,
                    "raw_diagnosis_from_record": item.raw_diagnosis,
                },
            )
            manifest["items"].append(
                {
                    "item_id": item.item_id,
                    "prompt_file": str(out.relative_to(ROOT)),
                    "raw_diagnosis": raw,
                }
            )
            items.append(item)
            print(f"wrote {out.name}")

        write_json(self.out_dir / "manifest.json", manifest)
        print(f"manifest -> {self.out_dir / 'manifest.json'}")
        return items

    @staticmethod
    def load_saved(prompt_dir: Path = PROMPT_DIR) -> list[dict]:
        files = sorted(prompt_dir.glob("D*.json"))
        if not files:
            raise SystemExit("No prompts. Run: python -m harness build")
        return [read_json(p) for p in files]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class BenchmarkRunner:
    """Same prompts -> one client -> verbatim artifacts on disk."""

    def __init__(self, client: LLMClient, raw_dir: Path = RAW_DIR):
        self.client = client
        self.raw_dir = raw_dir
        self.model_id = f"{client.provider}_{client.model.replace('/', '_')}"

    def run(self, prompts: list[dict] | None = None) -> Path:
        prompts = prompts or PromptBuilder.load_saved()
        out_dir = self.raw_dir / self.model_id
        out_dir.mkdir(parents=True, exist_ok=True)

        for p in prompts:
            item_id = p["item_id"]
            print(f"[{self.client.provider}/{self.client.model}] {item_id} ...")
            comp: Completion = self.client.complete(p["system_prompt"], p["user_prompt"])
            artifact = {
                "model_id": self.model_id,
                "provider": self.client.provider,
                "interface": "api",
                "model_name_requested": self.client.model,
                "model_name": comp.model_name,
                "endpoint": self.client.endpoint,
                "item_id": item_id,
                "patient_id": p["patient_id"],
                "visit_id": p["visit_id"],
                "system_prompt": p["system_prompt"],
                "user_prompt": p["user_prompt"],
                "raw_response": comp.text,
                "api_response_id": comp.response_id,
                "usage": comp.usage,
            }
            path = write_json(out_dir / f"{item_id}.json", artifact)
            preview = comp.text[:180].replace("\n", " ")
            print(f"  saved {path}")
            print(f"  preview: {preview}")
        return out_dir


def save_manual(
    item_id: str,
    provider: str,
    model_name: str,
    response_file: Path,
    prompt_dir: Path = PROMPT_DIR,
    raw_dir: Path = RAW_DIR,
) -> Path:
    """Website-chat path: paste verbatim reply into an artifact file."""
    prompt_path = next(prompt_dir.glob(f"{item_id}_*.json"), None)
    if not prompt_path:
        raise SystemExit(f"No prompt for {item_id}. Run build first.")
    prompt = read_json(prompt_path)
    raw = response_file.read_text(encoding="utf-8")
    model_id = f"{provider}_{model_name}".replace(" ", "_")
    artifact = {
        "model_id": model_id,
        "provider": provider,
        "interface": "website",
        "model_name": model_name,
        "item_id": prompt["item_id"],
        "patient_id": prompt["patient_id"],
        "visit_id": prompt["visit_id"],
        "system_prompt": prompt["system_prompt"],
        "user_prompt": prompt["user_prompt"],
        "raw_response": raw,
    }
    out = write_json(raw_dir / model_id / f"{item_id}.json", artifact)
    print(f"saved {out}")
    return out


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    t = text.lower().strip().replace("-", " ")
    t = re.sub(r"[^a-z0-9\s/+]", "", t)
    return re.sub(r"\s+", " ", t).strip()


class DiagnosisScorer:
    """Set F1 over gold conditions + critical clinical flags (negation / HLP sense)."""

    def __init__(self, gold_path: Path = GOLD_PATH, raw_dir: Path = RAW_DIR):
        self.gold_path = gold_path
        self.raw_dir = raw_dir

    @staticmethod
    def parse_conditions(raw_response: str, parsed_conditions=None) -> list[str]:
        if parsed_conditions is not None:
            return [str(x) for x in parsed_conditions]

        text = raw_response.strip()
        fence = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE
        )
        if fence:
            text = fence.group(1)
        else:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                text = m.group(0)

        try:
            obj = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return []

        conds = obj.get("conditions") or obj.get("diagnoses") or []
        names = []
        for c in conds:
            if isinstance(c, str):
                names.append(c)
            elif isinstance(c, dict):
                names.append(c.get("name") or c.get("label") or c.get("diagnosis") or "")
        return [n for n in names if n]

    @staticmethod
    def _match(name: str, gold_entry: dict) -> bool:
        n = _norm(name)
        cands = [_norm(c) for c in (
            gold_entry["label"],
            gold_entry["canonical_id"],
            *gold_entry.get("aliases", []),
        )]
        if n in cands:
            return True
        for c in cands:
            if c and min(len(c), len(n)) >= 3 and (c in n or n in c):
                return True
        return False

    def score_item(self, pred_names: list[str], gold_item: dict) -> dict:
        gold = gold_item["gold_conditions"]
        matched_gold: set[str] = set()
        matched_pred: set[int] = set()
        pairs = []

        # One pred can cover multiple golds ("CAD post CABG").
        for i, pname in enumerate(pred_names):
            hit = False
            for g in gold:
                if g["canonical_id"] in matched_gold:
                    continue
                if self._match(pname, g):
                    matched_gold.add(g["canonical_id"])
                    pairs.append({"pred": pname, "gold": g["canonical_id"]})
                    hit = True
            if hit:
                matched_pred.add(i)

        tp, fp = len(matched_gold), len(pred_names) - len(matched_pred)
        fn = len(gold) - len(matched_gold)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0

        flags = []
        joined = " | ".join(_norm(p) for p in pred_names)
        for excl in gold_item.get("explicitly_absent_or_excluded") or []:
            token = excl.get("token", "")
            if token == "no neuropathy":
                neu = {
                    "label": "neuropathy",
                    "canonical_id": "neuropathy",
                    "aliases": ["peripheral neuropathy", "diabetic neuropathy"],
                }
                if any(self._match(p, neu) for p in pred_names):
                    flags.append("FALSE_POSITIVE_NEUROPATHY")
            if token == "hlp_wrong_sense" and (
                "hyperkeratosis" in joined or "lenticularis" in joined
            ):
                flags.append("WRONG_HLP_SENSE_HYPERKERATOSIS")

        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "matched": pairs,
            "unmatched_preds": [p for i, p in enumerate(pred_names) if i not in matched_pred],
            "missed_gold": [g["canonical_id"] for g in gold if g["canonical_id"] not in matched_gold],
            "critical_flags": flags,
        }

    def score_all(self, out_path: Path = SCORES_PATH) -> dict:
        gold = read_json(self.gold_path)
        gold_by_id = {g["item_id"]: g for g in gold["items"]}  # type: ignore[index]
        results: dict = {"models": {}}

        if not self.raw_dir.exists():
            raise SystemExit(f"No raw outputs at {self.raw_dir}")

        for model_dir in sorted(p for p in self.raw_dir.iterdir() if p.is_dir()):
            model_scores: dict = {"items": {}, "macro_f1": None, "critical_flag_count": 0}
            f1s: list[float] = []
            for path in sorted(model_dir.glob("D*.json")):
                blob = read_json(path)
                item_id = blob.get("item_id") or path.stem  # type: ignore[union-attr]
                preds = self.parse_conditions(
                    blob.get("raw_response", ""),  # type: ignore[arg-type]
                    blob.get("parsed_conditions"),  # type: ignore[arg-type]
                )
                s = self.score_item(preds, gold_by_id[item_id])
                s["parsed_conditions"] = preds
                model_scores["items"][item_id] = s
                f1s.append(s["f1"])
                model_scores["critical_flag_count"] += len(s["critical_flags"])
            model_scores["macro_f1"] = round(sum(f1s) / len(f1s), 4) if f1s else None
            results["models"][model_dir.name] = model_scores
            print(
                model_dir.name,
                "macro_f1=",
                model_scores["macro_f1"],
                "critical_flags=",
                model_scores["critical_flag_count"],
            )

        write_json(out_path, results)
        print(f"wrote {out_path}")
        return results
