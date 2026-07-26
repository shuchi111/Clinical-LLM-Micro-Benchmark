#!/usr/bin/env python3
"""Shim - prefer: python -m harness run --provider gemini"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.cli import main

if __name__ == "__main__":
    main(["run", "--provider", "gemini"])
