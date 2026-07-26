# Step 2 - Benchmark Task Design

## Chosen task: Visit-level diagnosis extraction (from `raw_diagnosis`)

**Task.** Given only a visit-s `raw_diagnosis` token list (not the structured `diagnoses` field), extract the set of clinical conditions / relevant clinical status items that are affirmatively present. Expand common abbreviations to a canonical label. Exclude duration fragments, pure negations, and non-condition tokens unless they encode an affirmative clinical state (e.g. device/procedure history that is clinically material).

**What it measures.**
1. Abbreviation / shorthand understanding in real outpatient strings (`type 2 dm`, `cad post cabg`, `dm2`, `bph`, `ckd`, `hlp`).
2. Negation handling (`no neuropathy` ? do **not** assert neuropathy).
3. Filtering noise tokens that look diagnosis-like but aren-t (`24 years`).
4. Resistance to copying broken structured mappings (especially `hlp` ? hyperkeratosis lenticularis perstans).

**What would make the measurement invalid.**
- Treating structured `diagnoses` as gold (they are wrong on fixed items).
- Fuzzy free-text grading with no adjudicated label set.
- Allowing the model to see structured diagnoses or other visits- labels in the prompt.
- Scoring synonym mismatch as error when the clinical meaning is the same (need an alias table / equivalence rules).
- Tiny n=3 with no uncertainty statement - results are indicative, not a leaderboard.

## Fixed evaluation items (visit-level - this task)

| ID | Patient | Visit | Why it matters |
|----|---------|-------|----------------|
| D1 | P0006 | V00073 | Free text vs structured mismatch (pacemaker dropped) |
| D2 | P0003 | V00028 | Abbreviations + duration noise + duplicate CAD/CABG |
| D3 | P0010 | V00147 | Negation + dangerous `hlp` sense disambiguation |

Test-series HbA1c items are **out of scope** for this task family; noted in the report so comparison across candidates remains clear.

## Alternative considered and rejected

**Longitudinal HbA1c reasoning** ("has glycemic control worsened?" with mandatory date/value citations).

Rejected because: (1) the audit-s strongest integrity failure is diagnosis mapping/negation, which HbA1c never stresses; (2) the assignment-s visit-level fixed items are clearly built around free-text/structure mismatch and messy clinical language; (3) with n=3 series, a lab-trend task is almost a hand-check of arithmetic rather than a stress test of clinical NLP failure modes in *this* dump.

Medication normalization was a close second (especially V00147) but is weaker on V00073/V00028, where the dramatic bugs are diagnostic, not Rx.
