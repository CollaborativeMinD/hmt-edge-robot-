import pytest
from pydantic import ValidationError
from transitions.core import MachineError

from scaffoldctl.lifecycle import (
    STATE_DEFINITIONS,
    TRANSITION_RULES,
    TRANSITIONS_STATE_TABLE,
    LifecycleController,
)
from scaffoldctl.models import CriterionEvidence, ReopeningAuthorization, TransitionRequest
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import LIFECYCLE_STATE_ORDER, LifecycleState, LifecycleTrigger

CRITERION = "urn:scaffoldctl:criterion:test-admission"


def _request(
    trigger: LifecycleTrigger,
    *,
    admitted: bool = True,
    reopening: ReopeningAuthorization | None = None,
) -> TransitionRequest:
    return TransitionRequest(
        trigger=trigger,
        criteria=(
            CriterionEvidence(
                criterionIri=CRITERION,
                evidenceId=f"evidence:{trigger.value}",
                admitted=admitted,
            ),
        ),
        reopeningAuthorization=reopening,
    )


def test_native_state_definitions_match_owl_disjoint_union_order() -> None:
    assert tuple(item.name for item in STATE_DEFINITIONS) == tuple(
        state.value for state in LIFECYCLE_STATE_ORDER
    )
    assert len(TRANSITIONS_STATE_TABLE) == len(TRANSITION_RULES)
    assert all(item["conditions"] for item in TRANSITIONS_STATE_TABLE)


def test_primary_lifecycle_reaches_sealed() -> None:
    controller = LifecycleController()
    progression = (
        (LifecycleTrigger.PLAN, LifecycleState.PLANNED),
        (LifecycleTrigger.SCAFFOLD, LifecycleState.SCAFFOLDED_UNVALIDATED),
        (LifecycleTrigger.VALIDATE, LifecycleState.VALIDATED),
        (LifecycleTrigger.SEAL, LifecycleState.SEALED),
    )
    for trigger, expected in progression:
        receipt = controller.advance(_request(trigger))
        assert receipt.transitionAdmitted
        assert receipt.reasonCodes == (ReasonCode.TRANSITION_ADMITTED.value,)
        assert receipt.toState is expected
    terminal = controller.advance(_request(LifecycleTrigger.HOLD))
    assert not terminal.transitionAdmitted
    assert terminal.reasonCodes == (ReasonCode.TERMINAL_STATE_ABSORBING.value,)
    assert controller.state is LifecycleState.SEALED


def test_unsatisfied_criterion_does_not_advance() -> None:
    controller = LifecycleController()
    receipt = controller.advance(_request(LifecycleTrigger.PLAN, admitted=False))
    assert not receipt.transitionAdmitted
    assert receipt.reasonCodes == (ReasonCode.TRANSITION_CRITERIA_INVALID.value,)
    assert controller.state is LifecycleState.UNINITIALIZED


def test_unlisted_transition_does_not_advance() -> None:
    controller = LifecycleController()
    receipt = controller.advance(_request(LifecycleTrigger.SEAL))
    assert not receipt.transitionAdmitted
    assert receipt.reasonCodes == (ReasonCode.TRANSITION_NOT_ALLOWED.value,)
    assert controller.state is LifecycleState.UNINITIALIZED


def test_hold_reopening_requires_typed_authorization() -> None:
    controller = LifecycleController()
    assert controller.advance(_request(LifecycleTrigger.PLAN)).transitionAdmitted
    assert controller.advance(_request(LifecycleTrigger.HOLD)).transitionAdmitted
    denied = controller.advance(_request(LifecycleTrigger.REOPEN_PLANNED))
    assert not denied.transitionAdmitted
    assert denied.reasonCodes == (ReasonCode.REOPEN_AUTHORIZATION_INVALID.value,)
    authorization = ReopeningAuthorization(
        authorizationId="reopen:001",
        targetState=LifecycleState.PLANNED,
        reasonCode="SCF.REOPEN.AUTHORIZED",
        authorized=True,
    )
    admitted = controller.advance(
        _request(LifecycleTrigger.REOPEN_PLANNED, reopening=authorization)
    )
    assert admitted.transitionAdmitted
    assert controller.state is LifecycleState.PLANNED


def test_reopening_target_must_match_typed_trigger() -> None:
    controller = LifecycleController(LifecycleState.HOLD)
    authorization = ReopeningAuthorization(
        authorizationId="reopen:002",
        targetState=LifecycleState.VALIDATED,
        reasonCode="SCF.REOPEN.AUTHORIZED",
        authorized=True,
    )
    receipt = controller.advance(_request(LifecycleTrigger.REOPEN_PLANNED, reopening=authorization))
    assert not receipt.transitionAdmitted
    assert controller.state is LifecycleState.HOLD


def test_transition_request_requires_nonempty_unique_criteria() -> None:
    with pytest.raises(ValidationError):
        TransitionRequest(trigger=LifecycleTrigger.PLAN, criteria=())
    evidence = CriterionEvidence(
        criterionIri=CRITERION,
        evidenceId="evidence:duplicate",
        admitted=True,
    )
    with pytest.raises(ValidationError):
        TransitionRequest(trigger=LifecycleTrigger.PLAN, criteria=(evidence, evidence))


def test_auto_transitions_are_disabled() -> None:
    controller = LifecycleController()
    assert not hasattr(controller._model, "to_Planned")


def test_available_triggers_are_explicit() -> None:
    controller = LifecycleController()
    assert set(controller.available_triggers()) == {
        LifecycleTrigger.PLAN,
        LifecycleTrigger.HOLD,
        LifecycleTrigger.FAIL,
        LifecycleTrigger.REJECT,
    }


def test_controller_rejects_non_enum_initial_and_non_request() -> None:
    with pytest.raises(TypeError):
        LifecycleController("Uninitialized")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        LifecycleController().advance({})  # type: ignore[arg-type]


def test_machine_error_is_reason_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = LifecycleController()

    def fail(*args: object, **kwargs: object) -> None:
        raise MachineError("injected")

    monkeypatch.setattr(controller._model, "plan", fail)
    receipt = controller.advance(_request(LifecycleTrigger.PLAN))
    assert not receipt.transitionAdmitted
    assert receipt.reasonCodes == (ReasonCode.TRANSITION_SOURCE_INVALID.value,)
