import json, os, urllib.request, urllib.error
from pathlib import Path
profiles = [
 ("OPENAI_API_KEY", "https://api.openai.com/v1/models/gpt-4.1-mini-2025-04-14", "Authorization", "Bearer "),
 ("OPENAI_KEY", "https://api.openai.com/v1/models/gpt-4.1-mini-2025-04-14", "Authorization", "Bearer "),
 ("OPENAI", "https://api.openai.com/v1/models/gpt-4.1-mini-2025-04-14", "Authorization", "Bearer "),
 ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/key", "Authorization", "Bearer "),
 ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/models/claude-haiku-4-5-20251001", "x-api-key", ""),
 ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite", "x-goog-api-key", ""),
]
results = []
for name, url, header, prefix in profiles:
    key = os.environ.get(name, "")
    row = {"secret_name": name, "present": bool(key)}
    if key:
        req = urllib.request.Request(url, headers={header: prefix + key, "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read(16384))
                row.update(http_status=response.status, status="PASS")
                if name == "OPENROUTER_API_KEY":
                    data = payload.get("data", {})
                    row.update(limit_remaining=data.get("limit_remaining"), usage=data.get("usage"))
        except urllib.error.HTTPError as exc:
            row.update(http_status=exc.code, status="HOLD")
        except Exception as exc:
            row.update(status="HOLD", reason=type(exc).__name__)
    results.append(row)
result = {"scope": "metadata only; zero inference", "calls": 0, "usage_cost_usd": 0.0, "results": results}
Path("evidence").mkdir(exist_ok=True)
Path("evidence/provider_metadata.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
