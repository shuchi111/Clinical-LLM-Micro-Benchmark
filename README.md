# Clinical LLM Micro-Benchmark

Small, reproducible diagnosis-extraction benchmark on three fixed outpatient visits.

## Task

Extract affirmative conditions from `raw_diagnosis` tokens (not structured fields). See `TASK.md` and `DATA_AUDIT.md`.

## Setup

1. Copy `.env.example` -> `.env` and fill API keys (**never commit `.env`**).
2. Keep patient JSON / assignment PDF / field dictionary in local **`doc/`** (gitignored).

## Harness (OOP, one entrypoint)

```text
harness/
  config.py      # paths, prompts, .env
  clients.py     # ZAIClient / GroqClient / GeminiClient
  pipeline.py    # PromptBuilder, BenchmarkRunner, DiagnosisScorer
  cli.py         # python -m harness ...
```

```bash
# from project root
python -m harness build
python -m harness run --provider zai      # or: groq | gemini | all
python -m harness score
```

Legacy shims still work (`python harness/run_zai.py`, etc.).

### Website chat (allowed)

```bash
python -m harness save --item D1 --provider openai_website --model-name "GPT-4o" --response-file reply.txt
```

## Deliverables

- `REPORT.md` - write-up + transcript appendix
- `gold/` - labels + labeling protocol
- `outputs/raw/` - verbatim prompts/responses
- **Do not commit** `doc/` or `.env`
