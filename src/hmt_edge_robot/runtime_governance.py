"""RobotCell: governance responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .contracts import Policy
from .resident import QualifiedResidentProvider
from .vision import synthetic_frame

if TYPE_CHECKING:
    from hmt_edge_robot.runtime import RobotCell

def resident_tool(self: RobotCell, action: str, session_id: str, operator_id: str) -> Any:
    with self.lock:
        if not self.access.authorize(session_id, operator_id, "inspect", self.clock()):
            raise PermissionError("TOOL_AUTHORITY_NOT_ADMITTED")
        if action == "inspect":
            result = self.status()
        elif action == "diagnose":
            result = {
                "sensor_trends": self.analytics.sensor_trends(),
                "event_summary": self.analytics.summary(),
                "assurance_summary": self.assurance.analytics.summary(),
            }
        elif action == "plan_grasp":
            result = [
                r.model_dump(mode="json") for r in self.vision.candidates(synthetic_frame())
            ]
        elif action == "hold":
            result = {"decision": "HOLD"}
        else:
            raise PermissionError("TOOL_NOT_ALLOWLISTED")
        self.ledger.append(
            "resident", operator_id, "tool_result", {"action": action, "result": result}
        )
        return result

def update_policy(self: RobotCell, policy: Policy, session_id: str, operator_id: str) -> None:
    """Human configuration authority; revoke leases and pending model qualification."""
    with self.lock:
        if not self.access.authorize(session_id, operator_id, "reset", self.clock()):
            raise PermissionError("POLICY_AUTHORITY_NOT_ADMITTED")
        if policy.policy_epoch <= self.policy.policy_epoch:
            raise ValueError("POLICY_EPOCH_NOT_ADVANCED")
        self.ledger.append(
            "policy", operator_id, "policy_changed", {"policy": policy.model_dump(mode="json")}
        )
        self.policy = policy
        for component in (
            self.access,
            self.safety,
            self.edge,
            self.orchestrator,
            self.resident,
        ):
            component.policy = policy
        self.access.sessions.clear()
        if isinstance(self.resident.provider, QualifiedResidentProvider):
            self.resident.provider.qualified = False
