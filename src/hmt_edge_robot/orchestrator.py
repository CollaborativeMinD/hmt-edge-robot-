"""Compatibility facade for the decomposed orchestrator interfaces."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from .access import AccessManager
from .contracts import MotionRequest, Policy
from .edge import WaialuaEdgeNode
from .ledger import Ledger
from .orchestrator_admission import _guard, _receipt, cancel, submit
from .orchestrator_driver import Driver as Driver
from .orchestrator_driver import Feedback as Feedback
from .orchestrator_driver import SimulationDriver as SimulationDriver
from .orchestrator_execution import _execute, _verify, run_next
from .orchestrator_recovery import _deadline, reset, stop
from .safety import HaloSafe


class FactoryOrchestrator:
    def __init__(
        self,
        policy: Policy,
        ledger: Ledger,
        access: AccessManager,
        safety: HaloSafe,
        edge: WaialuaEdgeNode,
        driver: Driver,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy, self.ledger, self.access = policy, ledger, access
        self.safety, self.edge, self.driver, self.clock = safety, edge, driver, clock
        self.lock = threading.RLock()
        self.queue: deque[MotionRequest] = deque()
        self.fault_count, self.stopped = 0, False

    _guard = _guard

    _receipt = _receipt

    submit = submit

    cancel = cancel

    run_next = run_next

    _execute = _execute

    _verify = _verify

    _deadline = _deadline

    stop = stop

    reset = reset
