from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final

from transitions import Machine, State
from transitions.core import EventData, MachineError

from scaffoldctl.models import LifecycleTransition, TransitionReceipt, TransitionRequest
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    LIFECYCLE_STATE_ORDER,
    LifecycleState,
    LifecycleTrigger,
)


@dataclass(frozen=True, slots=True)
class TransitionRule:
    trigger: LifecycleTrigger
    source: LifecycleState
    target: LifecycleState
    reopening: bool = False


def _terminal_rules(
    trigger: LifecycleTrigger,
    target: LifecycleState,
    sources: tuple[LifecycleState, ...],
) -> tuple[TransitionRule, ...]:
    return tuple(TransitionRule(trigger, source, target) for source in sources)


def _reopening_rules() -> tuple[TransitionRule, ...]:
    targets = (
        (LifecycleTrigger.REOPEN_PLANNED, LifecycleState.PLANNED),
        (
            LifecycleTrigger.REOPEN_SCAFFOLDED_UNVALIDATED,
            LifecycleState.SCAFFOLDED_UNVALIDATED,
        ),
        (LifecycleTrigger.REOPEN_VALIDATED, LifecycleState.VALIDATED),
    )
    return tuple(
        TransitionRule(trigger, LifecycleState.HOLD, target, reopening=True)
        for trigger, target in targets
    )


def _rules() -> tuple[TransitionRule, ...]:
    primary_specs = (
        (LifecycleTrigger.PLAN, LifecycleState.UNINITIALIZED, LifecycleState.PLANNED),
        (LifecycleTrigger.SCAFFOLD, LifecycleState.PLANNED, LifecycleState.SCAFFOLDED_UNVALIDATED),
        (
            LifecycleTrigger.VALIDATE,
            LifecycleState.SCAFFOLDED_UNVALIDATED,
            LifecycleState.VALIDATED,
        ),
        (LifecycleTrigger.SEAL, LifecycleState.VALIDATED, LifecycleState.SEALED),
    )
    primary = tuple(TransitionRule(*spec) for spec in primary_specs)
    governed_sources = (
        LifecycleState.UNINITIALIZED,
        LifecycleState.PLANNED,
        LifecycleState.SCAFFOLDED_UNVALIDATED,
        LifecycleState.VALIDATED,
    )
    failure_sources = (*governed_sources, LifecycleState.HOLD)
    hold = _terminal_rules(LifecycleTrigger.HOLD, LifecycleState.HOLD, governed_sources)
    fail = _terminal_rules(LifecycleTrigger.FAIL, LifecycleState.FAIL, failure_sources)
    reject = _terminal_rules(LifecycleTrigger.REJECT, LifecycleState.REJECTED, failure_sources)
    return primary + hold + fail + reject + _reopening_rules()


TRANSITION_RULES: Final = _rules()
STATE_DEFINITIONS: Final = tuple(State(name=state.value) for state in LIFECYCLE_STATE_ORDER)
TRANSITIONS_STATE_TABLE: Final = tuple(
    {
        "trigger": rule.trigger.value,
        "source": rule.source.value,
        "dest": rule.target.value,
        "conditions": [
            "criteria_admitted",
            *(["reopening_admitted"] if rule.reopening else []),
        ],
    }
    for rule in TRANSITION_RULES
)


def _validate_compiled_table() -> None:
    state_names = tuple(state.name for state in STATE_DEFINITIONS)
    if state_names != tuple(state.value for state in LIFECYCLE_STATE_ORDER):
        raise RuntimeError("compiled transitions states drifted from lifecycle authority")
    keys = tuple((rule.trigger, rule.source) for rule in TRANSITION_RULES)
    if len(set(keys)) != len(keys):
        raise RuntimeError("duplicate trigger/source entry in lifecycle table")
    allowed_states = set(LIFECYCLE_STATE_ORDER)
    if any(
        rule.source not in allowed_states or rule.target not in allowed_states
        for rule in TRANSITION_RULES
    ):
        raise RuntimeError("lifecycle table references a state outside the ontology union")


_validate_compiled_table()


class _LifecycleModel:
    def __init__(self, initial: LifecycleState) -> None:
        self.state = initial.value

    @staticmethod
    def criteria_admitted(event: EventData) -> bool:
        request = event.kwargs.get("request")
        return isinstance(request, TransitionRequest) and all(
            criterion.admitted for criterion in request.criteria
        )

    @staticmethod
    def reopening_admitted(event: EventData) -> bool:
        request = event.kwargs.get("request")
        if not isinstance(request, TransitionRequest) or request.reopeningAuthorization is None:
            return False
        authorization = request.reopeningAuthorization
        return authorization.authorized and authorization.targetState.value == event.transition.dest


class LifecycleController:
    def __init__(self, initial: LifecycleState = LifecycleState.UNINITIALIZED) -> None:
        if not isinstance(initial, LifecycleState):
            raise TypeError("initial must be LifecycleState")
        self._model = _LifecycleModel(initial)
        self._machine = Machine(
            model=self._model,
            states=tuple(State(name=state.value) for state in LIFECYCLE_STATE_ORDER),
            transitions=[dict(item) for item in TRANSITIONS_STATE_TABLE],
            initial=initial.value,
            auto_transitions=False,
            ignore_invalid_triggers=False,
            queued=False,
            send_event=True,
        )

    @property
    def state(self) -> LifecycleState:
        return LifecycleState(self._model.state)

    def available_triggers(self) -> tuple[LifecycleTrigger, ...]:
        return tuple(
            LifecycleTrigger(value) for value in self._machine.get_triggers(self.state.value)
        )

    def _rule_for(self, trigger: LifecycleTrigger) -> TransitionRule | None:
        return next(
            (
                rule
                for rule in TRANSITION_RULES
                if rule.trigger is trigger and rule.source is self.state
            ),
            None,
        )

    @staticmethod
    def _hash_receipt(payload: dict[str, object]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _receipt(
        self,
        *,
        request: TransitionRequest,
        source: LifecycleState,
        transition: LifecycleTransition | None,
        admitted: bool,
        reason: ReasonCode,
    ) -> TransitionReceipt:
        evidence_ids = tuple(item.evidenceId for item in request.criteria)
        if request.reopeningAuthorization is not None:
            evidence_ids = (*evidence_ids, request.reopeningAuthorization.authorizationId)
        payload: dict[str, object] = {
            "evidenceIds": evidence_ids,
            "fromState": source.value,
            "reasonCodes": [reason.value],
            "toState": self.state.value,
            "transition": None if transition is None else transition.model_dump(mode="json"),
            "transitionAdmitted": admitted,
            "trigger": request.trigger.value,
        }
        return TransitionReceipt(
            transition=transition,
            trigger=request.trigger,
            transitionAdmitted=admitted,
            fromState=source,
            toState=self.state,
            reasonCodes=(reason.value,),
            evidenceIds=evidence_ids,
            receiptHash=self._hash_receipt(payload),
        )

    def advance(self, request: TransitionRequest) -> TransitionReceipt:
        if not isinstance(request, TransitionRequest):
            raise TypeError("request must be TransitionRequest")
        source = self.state
        rule = self._rule_for(request.trigger)
        if rule is None:
            reason = (
                ReasonCode.TERMINAL_STATE_ABSORBING
                if source in (LifecycleState.SEALED, LifecycleState.FAIL, LifecycleState.REJECTED)
                else ReasonCode.TRANSITION_NOT_ALLOWED
            )
            return self._receipt(
                request=request,
                source=source,
                transition=None,
                admitted=False,
                reason=reason,
            )

        transition = LifecycleTransition(
            hasTransitionSource=rule.source,
            hasTransitionTarget=rule.target,
            validatesAgainst=tuple(item.criterionIri for item in request.criteria),
        )
        trigger = getattr(self._model, request.trigger.value)
        try:
            admitted = bool(trigger(request=request))
        except MachineError:
            return self._receipt(
                request=request,
                source=source,
                transition=transition,
                admitted=False,
                reason=ReasonCode.TRANSITION_SOURCE_INVALID,
            )

        if admitted:
            reason = ReasonCode.TRANSITION_ADMITTED
        elif rule.reopening:
            reason = ReasonCode.REOPEN_AUTHORIZATION_INVALID
        else:
            reason = ReasonCode.TRANSITION_CRITERIA_INVALID
        return self._receipt(
            request=request,
            source=source,
            transition=transition,
            admitted=admitted,
            reason=reason,
        )
