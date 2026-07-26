# Step 1 - Data Audit

Scope: the three provided patients only (`P0006`, `P0003`, `P0010`). Observations below are from reading the JSON, not from the schema dictionary alone.

## What's here

| Patient | Visits | Test series | HbA1c readings | Span (HbA1c) |
|---------|--------|-------------|----------------|--------------|
| P0006   | 32     | 128 names   | 23             | 2018-04 ? 2026-03 |
| P0003   | 17     | 86 names    | 10             | 2018-09 ? 2023-05 |
| P0010   | 8      | 20 names    | 5              | 2021-01 ? 2024-04 |

Each patient has `visit_list` (diagnoses, medications, free-text-ish fields, sparse notes) and `test_list` (list of `{test_name, readings:[{date,value,units}]}`). Visit-level `lab_values` is **always null** - labs live only in `test_list`.

## What looks usable

- **HbA1c time series**: dated numeric strings with `%` units; counts match the assignment (23 / 10 / 5). Good for longitudinal questions if answers must cite date+value.
- **Medication `rx_med_name`**: messy but present; many rows also have resolved `generic_name` / `generic_dose_name` (sometimes null).
- **`raw_diagnosis`**: list of short tokens (abbreviations, history fragments), not prose paragraphs. This is the richest visit-level signal for -what is actually written.-

## What's broken or untrustworthy (specific to these records)

1. **Structured `diagnoses` are not safe gold labels.**
   - `P0010/V00147`: raw `hlp` is mapped to **hyperkeratosis lenticularis perstans**. In this outpatient diabetes context, `hlp` almost certainly means **hyperlipidemia** (and the same wrong mapping appears on every P0010 visit that has `hlp`).
   - Same visit: raw `no neuropathy` is mapped to positive **neuropathy** - negation is ignored (`is_negated` is still `false`).
   - `P0006/V00073`: raw includes `pacemaker implanted`; structured list drops it entirely (and this pattern holds across all 32 P0006 visits).
   - `P0003/V00028`: raw includes duration fragment `24 years` and a duplicated `cad post cabg`; structured expands abbreviations reasonably (T2DM, CAD, CABG, HTN) but treating structured output as ground truth would hide the raw mess.

2. **`raw_diagnosis` mixes diagnoses with non-diagnoses.**
   Examples: `24 years` (duration), `no vaccination`, `no neuropathy` (negations), `pacemaker implanted` (procedure/device history), duplicated tokens.

3. **Notes and timestamps are often empty shells.**
   - Many note fields are the string `'[]'`, not empty lists / null.
   - Fixed visits have `created_on` / `dms_date_time` = null.
   - `raw_complaints` is null for essentially all P0006 and P0003 visits; P0010 has real complaint tokens.

4. **`test_list` contains junk / non-lab names.**
   - `blank text` ? value `Not Found`
   - `custom test` with opaque numeric/string values
   - Drug name `amoxicillin` appears as a -test- with values `Absent`
   A naive -use every test_name- pipeline would invent clinical meaning.

5. **Medication fields are inconsistent.**
   - `rx_duration = -1` means -not mentioned- (per dictionary), not a real duration.
   - `rx_frequency` can be null while `rx_dose` / `rx_usage` are filled (`ziltax` on V00073).
   - Unresolved generics: e.g. `ab phyllin sr tablet`, `inj f0ndastar 2.5 sc` (likely fondaparinux typo).
   - Alternate brand slash-strings: `p 650mg / xykaa 650mg tablet`, `levet m / lasma lc tablet`.

## What would trip up a naive benchmark

- Using structured `diagnoses` as labels ? rewards models that copy the **wrong** mapper (HLP ? rare dermatology disease; negated neuropathy ? positive).
- Scoring medication -normalization- against `generic_name` without adjudication ? fails when generic is null or when the interesting error is in the raw string.
- Asking models to -summarize the chart- without requiring citations ? free hallucination over 100+ test names, including junk series.
- Ignoring that `raw_diagnosis` is a **token list**, not a clinical note paragraph ? prompt design and expected output format matter.

## Bottom line for task design

The data-s sharpest, most assignment-aligned failure mode is **visit free-text vs structured diagnosis mismatch**, especially negation and abbreviation sense. Longitudinal HbA1c is cleaner numerically but does not exercise the visit-level traps the fixed set highlights.
