"""Compatibility facade for the decomposed contracts interfaces."""

from __future__ import annotations

from .contracts_base import EffectKind as EffectKind
from .contracts_base import Hash as Hash
from .contracts_base import MutationAction as MutationAction
from .contracts_base import Refs as Refs
from .contracts_base import Text as Text
from .contracts_base import Verdict as Verdict
from .contracts_effects import Effect as Effect
from .contracts_effects import EffectContract as EffectContract
from .contracts_effects import EffectTrace as EffectTrace
from .contracts_identity import ArtifactIdentity as ArtifactIdentity
from .contracts_identity import ArtifactRecord as ArtifactRecord
from .contracts_identity import Epochs as Epochs
from .contracts_identity import WitnessScope as WitnessScope
from .contracts_reclamation import Census as Census
from .contracts_reclamation import MutationGrant as MutationGrant
from .contracts_reclamation import ReclamationPlan as ReclamationPlan
from .contracts_recovery import RecoverySpec as RecoverySpec
from .contracts_recovery import RecoveryTrace as RecoveryTrace
from .contracts_recovery import StageObservation as StageObservation
from .contracts_recovery import WarmCandidate as WarmCandidate
from .contracts_reports import AssuranceReport as AssuranceReport
from .contracts_reports import SealedReport as SealedReport


