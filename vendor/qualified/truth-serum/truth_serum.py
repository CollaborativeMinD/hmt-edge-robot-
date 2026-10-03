#!/usr/bin/env python3
"""Repository admission entry point."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main() -> int:
    source = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(source))
    from truth_serum_runtime.cli import main as runtime_main

    return runtime_main()


if __name__ == "__main__":
    raise SystemExit(main())
