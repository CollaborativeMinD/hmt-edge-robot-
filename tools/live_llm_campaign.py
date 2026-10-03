"""Compatibility facade for the decomposed live_llm_campaign interfaces."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from live_llm_campaign_provider import campaign as campaign
from live_llm_campaign_provider import completed as completed


def main() -> None:
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        result = {
            "status": "HOLD",
            "rejection_reason": "REPEATED_CAMPAIGN_NOT_AUTHORIZED",
            "calls": 0,
        }
    else:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        result = (
            asyncio.run(campaign(key))
            if key
            else {
                "status": "HOLD",
                "rejection_reason": "OPENROUTER_SECRET_UNAVAILABLE",
                "calls": 0,
                "usage_cost_usd": 0.0,
            }
        )
    output = Path("evidence/live_llm_campaign.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if result["status"] == "FAIL":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
