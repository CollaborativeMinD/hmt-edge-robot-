"""REQ-SYS-01: one composed cell; driver and model seams remain replaceable."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .access import AccessManager, ProvisionedIdentity
from .analytics import Analytics
from .contracts import Policy, PositionPacket, SensorSample, digest
from .edge import WaialuaEdgeNode
from .geometry import Calibration
from .ledger import Ledger
from .orchestrator import FactoryOrchestrator, SimulationDriver
from .resident import ResidentHMT, ResidentProvider
from .safety import HaloSafe
from .vision import NeuroGrasp, synthetic_frame


class RobotCell:
    def __init__(self, database: Path, operator_token: str, policy: Policy | None = None,
                 provider: ResidentProvider | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        if len(operator_token) < 16:
            raise ValueError("OPERATOR_TOKEN_TOO_SHORT")
        self.policy, self.clock = policy or Policy(), clock
        self.ledger = Ledger(database)
        self.ledger.verify()
        self.ledger.recover()
        identity = ProvisionedIdentity({"operator": (digest(operator_token), ("inspect", "motion", "reset"))})
        self.access = AccessManager(identity, self.policy, self.ledger)
        self.safety, self.edge = HaloSafe(self.policy), WaialuaEdgeNode(self.policy, self.ledger)
        self.vision = NeuroGrasp(Calibration())
        self.driver = SimulationDriver()
        self.orchestrator = FactoryOrchestrator(self.policy, self.ledger, self.access, self.safety, self.edge, self.driver, clock)
        self.analytics, self.resident = Analytics(self.ledger), ResidentHMT(self.policy, self.ledger, provider)
        self.lock = self.orchestrator.lock

    def observe_simulation(self, seq: int, voltage_v: float = 4.1, temp_c: float = 45.0,
                           human_mm: tuple[float, float, float] = (3000.0, 0.0, 0.0)) -> None:
        """Explicit SIL acquisition; production observations require qualified adapters."""
        with self.lock:
            now = self.clock()
            self.edge.process(SensorSample(monotonic_seq=seq, observed_at=now, voltage_v=voltage_v, temp_c=temp_c, signal_dbm=-50.0), now)
            robot = PositionPacket(position_mm=self.driver.position, monotonic_seq=seq, observed_at=now)
            human = PositionPacket(position_mm=human_mm, monotonic_seq=seq, observed_at=now)
            self.safety.update(robot, human, now)
            self.ledger.append("safety", str(seq), "spatial_observation", {"robot": robot.model_dump(mode="json"), "human": human.model_dump(mode="json")})

    def status(self) -> dict[str, Any]:
        with self.lock:
            lane = self.edge.history[-1].pace_lane.value if self.edge.history else "CONTINGENCY"
            return {"stopped": self.orchestrator.stopped or self.safety.latched, "queue_size": len(self.orchestrator.queue),
                    "pace_lane": "EMERGENCY" if self.orchestrator.stopped else lane,
                    "substrate_ready": bool(self.edge.history and self.edge.history[-1].data_valid and not self.edge.halted)}

    def resident_tool(self, action: str, session_id: str, operator_id: str) -> Any:
        with self.lock:
            if not self.access.authorize(session_id, operator_id, "inspect", self.clock()):
                raise PermissionError("TOOL_AUTHORITY_NOT_ADMITTED")
            if action == "inspect":
                result = self.status()
            elif action == "diagnose":
                result = {"sensor_trends": self.analytics.sensor_trends(), "event_summary": self.analytics.summary()}
            elif action == "plan_grasp":
                result = [r.model_dump(mode="json") for r in self.vision.candidates(synthetic_frame())]
            elif action == "hold":
                result = {"decision": "HOLD"}
            else:
                raise PermissionError("TOOL_NOT_ALLOWLISTED")
            self.ledger.append("resident", operator_id, "tool_result", {"action": action, "result": result})
            return result

    def close(self) -> None:
        self.ledger.close()

    def update_policy(self, policy: Policy, session_id: str, operator_id: str) -> None:
        """Human configuration authority; revoke leases and pending model qualification."""
        with self.lock:
            if not self.access.authorize(session_id, operator_id, "reset", self.clock()):
                raise PermissionError("POLICY_AUTHORITY_NOT_ADMITTED")
            if policy.policy_epoch <= self.policy.policy_epoch:
                raise ValueError("POLICY_EPOCH_NOT_ADVANCED")
            self.ledger.append("policy", operator_id, "policy_changed", {"policy": policy.model_dump(mode="json")})
            self.policy = policy
            for component in (self.access, self.safety, self.edge, self.orchestrator, self.resident):
                component.policy = policy
            self.access.sessions.clear()
            if hasattr(self.resident.provider, "qualified"):
                self.resident.provider.qualified = False
