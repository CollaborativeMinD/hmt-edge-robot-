"""Evidence storage failure contract."""

class EvidenceError(RuntimeError):
    """Persistence or replay integrity failed; caller must stop admission."""
