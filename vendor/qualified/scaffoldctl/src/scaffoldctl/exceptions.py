from __future__ import annotations

from scaffoldctl.reason_codes import ReasonCode


class PhaseTwoError(RuntimeError):
    def __init__(
        self,
        reason_code: ReasonCode,
        message: str,
        *,
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.exit_code = exit_code


class TransactionError(PhaseTwoError):
    def __init__(
        self,
        message: str,
        *,
        rollback_complete: bool,
        created_paths: tuple[str, ...],
        error_class: str,
    ) -> None:
        reason = (
            ReasonCode.TRANSACTION_ROLLBACK_COMPLETE
            if rollback_complete
            else ReasonCode.TRANSACTION_ROLLBACK_FAILED
        )
        super().__init__(reason, message, exit_code=3)
        self.rollback_complete = rollback_complete
        self.created_paths = created_paths
        self.error_class = error_class


class PhaseThreeError(PhaseTwoError):
    """Fail-closed Phase 3 perimeter, lease, or ledger rejection."""
