#!/usr/bin/env python3
from __future__ import annotations

import sys

from scaffoldctl.cli import main

if __name__ == "__main__":
    raise SystemExit(main(("seal-ledger", *sys.argv[1:])))
