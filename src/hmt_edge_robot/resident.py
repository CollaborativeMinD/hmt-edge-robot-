"""Compatibility facade for the decomposed resident interfaces."""

from __future__ import annotations

from .resident_cloud import OpenAICompatibleProvider as OpenAICompatibleProvider
from .resident_governance import ResidentHMT as ResidentHMT
from .resident_health import HealthModel as HealthModel
from .resident_providers import CallBudget as CallBudget
from .resident_providers import DeterministicResident as DeterministicResident
from .resident_providers import QualifiedResidentProvider as QualifiedResidentProvider
from .resident_providers import ResidentProvider as ResidentProvider


