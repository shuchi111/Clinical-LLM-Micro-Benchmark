# Clinical LLM Micro-Benchmark - Report

## 1. Data audit (summary)

Three anonymized outpatient chronic-care patients (`P0006`, `P0003`, `P0010`) with `visit_list` + `test_list`. Visit-level `lab_values` is always null; labs live only in `test_list`. `raw_diagnosis` is a **token list**, not prose.

**Reliable enough for this task:** `raw_diagnosis` tokens as written; HbA1c dated series (not used here).

**Not trustworthy as labels:** structured `diagnoses`. On `P0010/V00147`, `hlp` is mapped to *hyperkeratosis lenticularis perstans* (wrong sense for this diabetes clinic context -> hyperlipidemia), and `no neuropathy` is mapped as positive neuropathy with `is_negated=false`. On `P0006`, `pacemaker implanted` is present in raw text across visits but absent from structured diagnoses. Note fields are often the string `"[]"`; `test_list` includes junk names (`blank text`, `custom test`).

Full notes: `DATA_AUDIT.md`.

## 2. Task

**Diagnosis extraction from `raw_diagnosis` only.** Expand abbreviations; honor negation; drop duration fragments; do not invent conditions.

**Measures:** abbreviation expansion, negation, noise filtering, resistance to the broken structured mapper (especially `hlp`).

**Invalidates the measurement:** using structured diagnoses as gold; fuzzy grading without adjudicated labels; leaking structured fields into the prompt; treating synonym mismatches as hard errors without an alias table.

**Rejected alternative:** longitudinal HbA1c reasoning. Cleaner numerically, but it never stresses the visit-level mapping/negation failures this dump's fixed visit items highlight.

Fixed **visit-level** items used: D1=`P0006/V00073`, D2=`P0003/V00028`, D3=`P0010/V00147`. HbA1c test-series items are out of scope for this task family.

## 3. Method

- **Gold:** hand-adjudicated from `raw_diagnosis` only (`gold/gold_labels.json`; protocol in `gold/LABELING_PROTOCOL.md`). Critical D3 gold: T2DM, coryza, hyperlipidemia; neuropathy and vaccination negation excluded; hyperkeratosis must not appear.
- **Harness:** identical system+user prompts for all models (`harness/build_prompts.py` -> `outputs/prompts/`). Temperature 0. Raw prompt+response saved under `outputs/raw/`.
- **Scoring:** condition-set precision/recall/F1 with alias matching; one prediction may cover multiple gold concepts (e.g. "CAD post CABG"). Critical flags for false-positive neuropathy / wrong `hlp` sense. With n=3 items, report per-item F1 and macro-F1; do not overclaim.

### Models (three providers, API)

| Provider | Interface | Requested model | Returned / recorded name |
|----------|-----------|-----------------|--------------------------|
| Z.AI | API (`api.z.ai` Anthropic-compatible) | `glm-5.1` | `glm-5.2` |
| Groq | API (OpenAI-compatible) | `llama-3.3-70b-versatile` | `llama-3.3-70b-versatile` |
| Google | API (`generativelanguage.googleapis.com`) | `gemini-2.5-flash` | `gemini-2.5-flash` |

(`gemini-2.0-flash` was attempted first; free-tier quota was exhausted / limit 0. Switched to `gemini-2.5-flash`, which succeeded.)

## 4. Results

Scores recomputed from saved raw outputs via `harness/score.py` -> `outputs/scores.json`.

| Model | D1 F1 | D2 F1 | D3 F1 | Macro-F1 | Critical flags |
|-------|-------|-------|-------|----------|----------------|
| Z.AI `glm-5.1`->`glm-5.2` | 1.00 | 1.00 | 1.00 | **1.00** | 0 |
| Groq `llama-3.3-70b-versatile` | 1.00 | 0.86 | 1.00 | **0.95** | 0 |
| Google `gemini-2.5-flash` | 1.00 | 1.00 | 1.00 | **1.00** | 0 |

**Per-item notes**
- **D1:** all three recovered pacemaker + expanded BPH/CKD/T2DM.
- **D2:** Groq extracted CAD from `cad post cabg` but not a separate post-CABG concept (missed `post_cabg` under our two-concept gold). Z.AI and Gemini emitted a combined CAD+CABG phrase that matched both golds under multi-concept matching.
- **D3 (hardest):** all three mapped `hlp`->hyperlipidemia, honored `no neuropathy`, ignored `no vaccination`. None copied the structured-field dermatology error.

**Uncertainty:** n=3 fixed items only. Macro-F1 differences are not statistically meaningful; the useful signal is the qualitative D2 splitting behavior and unanimous success on D3's sense/negation traps. Bootstrap CIs on n=3 would be decorative, so omitted.

## 5. Threats to validity

1. **Tiny fixed set** - three visits; one error flips macro-F1 a lot (as with Groq D2).
2. **Single-annotator gold** - especially `hlp`->hyperlipidemia (clinically plausible here, but not lab-confirmed in-visit).
3. **Alias / multi-match scoring** - generous equivalence can hide over-/under-splitting of compound tokens (`cad post cabg`).
4. **Prompt teaches the rules** - negation and "ignore duration" are explicit; this measures instruction-following + abbreviation sense more than unaided clinical NLP.
5. **Provider routing** - Z.AI request said `glm-5.1` but response metadata said `glm-5.2`; we report both.
6. **No structured-field leakage check beyond file inspection** - prompts contain only `raw_diagnosis` by construction.

## 6. AI tools note

AI assistance was used to scaffold the harness, draft audit/report text, and iterate scoring. The gold labels and the decision to distrust structured diagnoses came from **manual inspection of these three records** (notably D3's `hlp` / `no neuropathy`). Early API probing also showed that trusting env "OpenAI" keys without checking the actual endpoint/provider would have mislabeled runs.

---

## Appendix - Verbatim transcripts (items D1 and D3)

Identical prompts for all models. Responses are unedited.

### Shared system prompt

```
You are a clinical information extraction assistant.
Extract diagnoses/conditions that are AFFIRMATIVELY present from the raw_diagnosis token list.
Rules:
- Expand common clinical abbreviations to clear English labels.
- Do NOT invent conditions that are not supported by the tokens.
- Ignore duration-only fragments (e.g. "24 years").
- Honor negation: tokens like "no X" mean X is NOT present.
- Output JSON only, with this schema:
{"conditions":[{"name":"<label>","evidence_token":"<exact token from input>"}]}
- Deduplicate. No prose outside JSON.
```

### Item D1 - P0006 / V00073

**User prompt**

```
Patient ID: P0006
Visit ID: V00073

raw_diagnosis tokens:
[
  "hypertension",
  "pacemaker implanted",
  "bph",
  "ckd",
  "type 2 dm",
  "atrial fibrillation"
]

Extract affirmative conditions as JSON.
```

**Z.AI (`glm-5.1` requested, `glm-5.2` returned)**

```
```json
{
  "conditions": [
    {
      "name": "hypertension",
      "evidence_token": "hypertension"
    },
    {
      "name": "pacemaker implanted",
      "evidence_token": "pacemaker implanted"
    },
    {
      "name": "benign prostatic hyperplasia",
      "evidence_token": "bph"
    },
    {
      "name": "chronic kidney disease",
      "evidence_token": "ckd"
    },
    {
      "name": "type 2 diabetes mellitus",
      "evidence_token": "type 2 dm"
    },
    {
      "name": "atrial fibrillation",
      "evidence_token": "atrial fibrillation"
    }
  ]
}
```
```

**Groq (`llama-3.3-70b-versatile`)**

```
{"conditions":[
  {"name":"Hypertension","evidence_token":"hypertension"},
  {"name":"Pacemaker Implanted","evidence_token":"pacemaker implanted"},
  {"name":"Benign Prostatic Hyperplasia","evidence_token":"bph"},
  {"name":"Chronic Kidney Disease","evidence_token":"ckd"},
  {"name":"Type 2 Diabetes Mellitus","evidence_token":"type 2 dm"},
  {"name":"Atrial Fibrillation","evidence_token":"atrial fibrillation"}
]}
```

**Google (`gemini-2.5-flash`)**

```
```json
{
  "conditions": [
    {
      "name": "Hypertension",
      "evidence_token": "hypertension"
    },
    {
      "name": "Pacemaker implanted",
      "evidence_token": "pacemaker implanted"
    },
    {
      "name": "Benign Prostatic Hyperplasia",
      "evidence_token": "bph"
    },
    {
      "name": "Chronic Kidney Disease",
      "evidence_token": "ckd"
    },
    {
      "name": "Type 2 Diabetes Mellitus",
      "evidence_token": "type 2 dm"
    },
    {
      "name": "Atrial Fibrillation",
      "evidence_token": "atrial fibrillation"
    }
  ]
}
```
```

### Item D3 - P0010 / V00147

**User prompt**

```
Patient ID: P0010
Visit ID: V00147

raw_diagnosis tokens:
[
  "dm2",
  "coryza",
  "no vaccination",
  "hlp",
  "no neuropathy"
]

Extract affirmative conditions as JSON.
```

**Z.AI (`glm-5.1` requested, `glm-5.2` returned)**

```
{"conditions":[{"name":"Type 2 Diabetes Mellitus","evidence_token":"dm2"},{"name":"Coryza","evidence_token":"coryza"},{"name":"Hyperlipidemia","evidence_token":"hlp"}]}
```

**Groq (`llama-3.3-70b-versatile`)**

```
{"conditions":[{"name":"Diabetes Mellitus Type 2","evidence_token":"dm2"},{"name":"Common Cold","evidence_token":"coryza"},{"name":"Hyperlipidemia","evidence_token":"hlp"}]}
```

**Google (`gemini-2.5-flash`)**

```
```json
{
  "conditions": [
    {
      "name": "Diabetes Mellitus Type 2",
      "evidence_token": "dm2"
    },
    {
      "name": "Coryza",
      "evidence_token": "coryza"
    },
    {
      "name": "Hyperlipidemia",
      "evidence_token": "hlp"
    }
  ]
}
```
```

Artifacts: `outputs/raw/{provider_model}/D{1,2,3}.json`, `gold/`, `harness/`. Patient JSON is intentionally not in the repo.
