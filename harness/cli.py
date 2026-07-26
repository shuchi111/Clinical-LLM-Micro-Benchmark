"""CLI: python -m harness <build|run|score|save>"""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.clients import make_client
from harness.config import load_dotenv
from harness.pipeline import BenchmarkRunner, DiagnosisScorer, PromptBuilder, save_manual


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harness",
        description="Clinical LLM micro-benchmark: build prompts, run models, score.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="Build identical prompts from gold x patient JSON")

    run = sub.add_parser("run", help="Run one or all providers on saved prompts")
    run.add_argument(
        "--provider",
        required=True,
        choices=["zai", "groq", "gemini", "google", "all"],
        help="Which API provider to call",
    )

    sub.add_parser("score", help="Score outputs/raw against gold labels")

    save = sub.add_parser("save", help="Save a website-chat verbatim reply")
    save.add_argument("--item", required=True, help="D1 | D2 | D3")
    save.add_argument("--provider", required=True)
    save.add_argument("--model-name", required=True)
    save.add_argument("--response-file", required=True, type=Path)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    load_dotenv()

    if args.cmd == "build":
        PromptBuilder().build()
        return

    if args.cmd == "run":
        names = ["zai", "groq", "gemini"] if args.provider == "all" else [args.provider]
        for name in names:
            client = make_client(name)
            BenchmarkRunner(client).run()
        return

    if args.cmd == "score":
        DiagnosisScorer().score_all()
        return

    if args.cmd == "save":
        save_manual(
            item_id=args.item,
            provider=args.provider,
            model_name=args.model_name,
            response_file=args.response_file,
        )
        return


if __name__ == "__main__":
    main()
