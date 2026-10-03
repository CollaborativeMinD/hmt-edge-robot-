"""REQ-SYS-01: one composed cell; driver and model seams remain replaceable."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .access import AccessManager, ProvisionedIdentity
from .analytics import Analytics
from .assurance import SubstrateAssurance
from .contracts import Policy, digest
from .edge import WaialuaEdgeNode
from .geometry import Calibration
from .ledger import Ledger
from .orchestrator import FactoryOrchestrator, SimulationDriver
from .resident import ResidentHMT, ResidentProvider
from .runtime_governance import resident_tool, update_policy
from .runtime_simulation import observe_simulation
from .safety import HaloSafe
from .vision import NeuroGrasp


class RobotCell:
    def __init__(
        self,
        database: Path,
        operator_token: str,
        policy: Policy | None = None,
        provider: ResidentProvider | None = None,
        clock: Callable[[], float] = time.monotonic,
        read_only: bool = False,
    ) -> None:
        if len(operator_token) < 16:
            raise ValueError("OPERATOR_TOKEN_TOO_SHORT")
        self.policy, self.clock = policy or Policy(), clock
        self.ledger = Ledger(database, read_only=read_only)
        self.ledger.verify()
        if not read_only:
            self.ledger.recover()
        identity = ProvisionedIdentity(
            {"operator": (digest(operator_token), ("inspect", "motion", "reset"))}
        )
        self.access = AccessManager(identity, self.policy, self.ledger)
        self.safety, self.edge = HaloSafe(self.policy), WaialuaEdgeNode(self.policy, self.ledger)
        self.vision = NeuroGrasp(Calibration())
        self.driver = SimulationDriver()
        self.orchestrator = FactoryOrchestrator(
            self.policy, self.ledger, self.access, self.safety, self.edge, self.driver, clock
        )
        self.analytics, self.resident = (
            Analytics(self.ledger),
            ResidentHMT(self.policy, self.ledger, provider),
        )
        self.lock = self.orchestrator.lock
        self.assurance = SubstrateAssurance(self, read_only=read_only)

    observe_simulation = observe_simulation

    def status(self) -> dict[str, Any]:
        with self.lock:
            lane = self.edge.history[-1].pace_lane.value if self.edge.history else "CONTINGENCY"
            return {
                "stopped": self.orchestrator.stopped or self.safety.latched,
                "queue_size": len(self.orchestrator.queue),
                "pace_lane": "EMERGENCY" if self.orchestrator.stopped else lane,
                "substrate_ready": bool(
                    self.edge.history and self.edge.history[-1].data_valid and not self.edge.halted
                ),
            }

    resident_tool = resident_tool

    def close(self) -> None:
        self.ledger.close()

    update_policy = update_policy
