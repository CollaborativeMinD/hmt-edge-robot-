"""SIL service/storage readiness only; never mission or physical readiness."""
import json
import sqlite3
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as response:
    if json.load(response) != {"status": "alive", "mode": "SIL"}:
        raise SystemExit(1)
with sqlite3.connect("file:/data/cell.db?mode=ro", uri=True, timeout=2) as database:
    if database.execute("PRAGMA quick_check").fetchone() != ("ok",):
        raise SystemExit(1)
