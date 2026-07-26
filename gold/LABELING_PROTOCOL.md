# Gold labels - diagnosis extraction

## Labeling protocol

1. **Source of truth:** only the visit-s `raw_diagnosis` token list. Structured `diagnoses`, medications, complaints, and labs were **not** used as labels (they are known-wrong on at least one fixed item).
2. **Include:** affirmative disease/condition mentions and clinically material status that a clinician would retain from the token (e.g. pacemaker in situ / implanted). Expand abbreviations to a canonical English label.
3. **Exclude:** duration-only fragments (`24 years`); tokens that are pure negations of a finding (`no neuropathy`, `no vaccination`); exact duplicate mentions (count once).
4. **Sense disambiguation:** `hlp` in this diabetes/outpatient meds context ? **hyperlipidemia**, not the rare dermatologic expansion present in the structured field.
5. **Equivalence for scoring:** a model answer matches a gold item if it normalizes to the same `canonical_id` after lowercasing, stripping punctuation, and applying the alias list in `gold_labels.json`.

Adjudicator: single human pass over the three fixed visits after reading full visit medication context for sense checks only (not as extra diagnoses).
