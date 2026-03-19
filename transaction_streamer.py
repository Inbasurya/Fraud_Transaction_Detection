#!/usr/bin/env python3
"""Project-level launcher for streaming transactions."""

from pathlib import Path
import runpy

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "data" / "transaction_streamer.py"
    runpy.run_path(str(target), run_name="__main__")
