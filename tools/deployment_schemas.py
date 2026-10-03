"""Published contracts include both success and fail-closed rejection variants."""

from __future__ import annotations

from typing import Any

from deployment_contracts import DeploymentPlan
from deployment_io import DeploymentCatalog
from deployment_receipts import OUTCOME, ReleaseCandidate


def contract_schemas() -> dict[str, dict[str, Any]]:
    return {"deployment-plan": DeploymentPlan.model_json_schema(),
            "release-candidate": ReleaseCandidate.model_json_schema(),
            "release-receipt": OUTCOME.json_schema(),
            "deployment-catalog": DeploymentCatalog.model_json_schema()}
