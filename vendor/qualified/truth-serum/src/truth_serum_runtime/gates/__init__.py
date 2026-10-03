"""Local deterministic admission gates."""

from .aperture import run as source_aperture
from .architecture import run as architecture_trace
from .claims import run as evidence_binding
from .data import run as structured_data
from .secrets import run as secret_scan
from .shape import run as repository_shape
from .shell import run as shell_syntax

__all__ = [
    "architecture_trace",
    "evidence_binding",
    "repository_shape",
    "secret_scan",
    "shell_syntax",
    "source_aperture",
    "structured_data",
]
