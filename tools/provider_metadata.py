import json, os, urllib.request, urllib.error
from pathlib import Path
key = os.environ.get("OPENAI_API_KEY", "")
result = {"scope": "metadata only; zero inference", "calls": 0, "usage_cost_usd": 0.0}
if key:
    req = urllib.request.Request("https://api.openai.com/v1/models/gpt-4.1-mini-2025-04-14", headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read(16384))
            result.update(status="PASS", http_status=response.status, model_id=payload.get("id"))
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read(16384))
        error = payload.get("error", {})
        allowed = {"invalid_api_key", "insufficient_quota", "model_not_found", "invalid_request_error", "authentication_error", "permission_error"}
        result.update(status="HOLD", http_status=exc.code, provider_code=error.get("code") if error.get("code") in allowed else "UNCLASSIFIED")
else:
    result.update(status="HOLD", reason="SECRET_UNAVAILABLE")
Path("evidence").mkdir(exist_ok=True)
Path("evidence/provider_metadata.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
