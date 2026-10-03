# Executable Command Surfaces

| Command | Input and bounds | Output and authority |
|---|---|---|
| `python3 tools/ci_admission.py` | Reviewed catalog; bounded regular files | Integrity receipt; no installation or promotion |
| `uv run --no-sync python tools/policy_evaluation.py` | Pinned HMT declarations; at most 256 Python files | Source-bound human promotion, enforced ceilings and disposition receipt |
| `uv run --no-sync python tools/ci_profiles.py` | Three root documents and bounded evidence claims | Read-only scaffold and evidence-binding receipts |
| `uv run --no-sync python tools/deployment_gate.py` | Strict stage-3 catalog, plan and dormant templates | Deterministic design receipt; release stays HOLD |
| `uv run --no-sync python tools/deployment_campaign.py` | Bounded negative test suite | Rejection and coverage evidence; no deployment |
| `uv run --no-sync python tools/validate.py` | Locked software environment | Cumulative software gates; deployment remains HOLD |

These are CI support commands. No MCP server, hook installation, signing lease,
full Truth Serum engine admission, container build, or deployment is exposed here.
