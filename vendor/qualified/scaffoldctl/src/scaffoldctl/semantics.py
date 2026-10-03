from enum import StrEnum
from typing import Final

SC_NAMESPACE: Final = "urn:scaffoldctl:ontology:semantic-scaffolding#"
ONTOLOGY_IRI: Final = "urn:scaffoldctl:ontology:semantic-scaffolding"
ONTOLOGY_VERSION_IRI: Final = "urn:scaffoldctl:ontology:semantic-scaffolding:1.0.0"
ONTOLOGY_VERSION: Final = "1.0.0"
ONTOLOGY_PROVENANCE_ID: Final = "prov_semantic_scaffolding_plan_20260803_v1_0_0"
ONTOLOGY_ARTIFACT_DISPOSITION: Final = "new"
ONTOLOGY_CREATED_ON: Final = "2026-08-03"
ONTOLOGY_SHA256: Final = "875b9ec0d714b8757c2172ea844d8ecfe6150feac2649b0205239aa64534650b"
PACKAGE_VERSION: Final = "0.3.0"
PROMOTED_BASELINE_ARCHIVE_SHA256: Final = (
    "bcc613bde53a6bdb4e6ebe023a21d954a47768537a916b8b34709fc96ad81347"
)
PROMOTION_RECEIPT_ID: Final = "b12dea24-d474-4778-9dde-690ac0c480db"
PROMOTION_RECEIPT_SHA256: Final = "edacf25a035abdc9df1af874fdde7c864ef928f5f041db8f0c8ed2a4b8cd0f8b"
PROMOTION_REPORT_SHA256: Final = "d990cc6b86a8072befefd850c9299bfa655bfa6eb03b07ad5e6feb3fc39ba5f0"
PHASE_TWO_POLICY_PACK_SHA256: Final = (
    "3523ca97954bb8a3ee70dfb1e8f96f0f8d70c3b2aacca27489916b6aa62ce3cd"
)
PHASE_TWO_TEMPLATE_PACK_SHA256: Final = (
    "48c34b583b4f8f6cc416583100448967f87f3055b11acf11ac02f90aeed03e30"
)
PHASE_TWO_POLICY_FILE_NAME: Final = "scaffold.policy.json"
PHASE_THREE_UPSTREAM_ARCHIVE_SHA256: Final = (
    "99f55164c2c8dab3dae1db9119f99511428d561f61f316d96f64f29e060f8bd8"
)
PHASE_THREE_UPSTREAM_WHEEL_SHA256: Final = (
    "5a4b17c9cd0148740cba0245e731281aceb7f1779b3886fa0b1904f8fcda3726"
)
PHASE_THREE_SUBMITTED_TOKEN: Final = "99f55164c2c8dab3dae1db9119f9511428d561f316d96f64f29e060f8bd8"
PHASE_THREE_LEDGER_SCHEMA_ID: Final = "urn:scaffoldctl:duckdb-ledger:0.3.0"
PHASE_THREE_LEDGER_SCHEMA_VERSION: Final = "0.3.0"
PHASE_THREE_ZERO_HASH: Final = "0" * 64


class LifecycleState(StrEnum):
    UNINITIALIZED = "Uninitialized"
    PLANNED = "Planned"
    SCAFFOLDED_UNVALIDATED = "ScaffoldedUnvalidated"
    VALIDATED = "Validated"
    SEALED = "Sealed"
    HOLD = "Hold"
    FAIL = "Fail"
    REJECTED = "Rejected"


class LifecycleTrigger(StrEnum):
    PLAN = "plan"
    SCAFFOLD = "scaffold"
    VALIDATE = "validate"
    SEAL = "seal"
    HOLD = "hold"
    FAIL = "fail"
    REJECT = "reject"
    REOPEN_PLANNED = "reopen_planned"
    REOPEN_SCAFFOLDED_UNVALIDATED = "reopen_scaffolded_unvalidated"
    REOPEN_VALIDATED = "reopen_validated"


LIFECYCLE_STATE_ORDER: Final = tuple(LifecycleState)
HMT_REQUIRED_PATHS: Final = ("README.md", "Start_here.md", "Index.md")
HMT_MAXIMUM_LINE_COUNT_EXCLUSIVE: Final = 100
HMT_MINIMUM_LINE_COUNT: Final = 0
SHACL_NODE_SHAPES: Final = (
    "HMTTrifectaDocumentShape",
    "IndexDocumentShape",
    "ReadmeDocumentShape",
    "RepositoryRootDirectoryShape",
    "StartHereDocumentShape",
)


class ArtifactDisposition(StrEnum):
    NEW = "new"
    MODIFIED = "modified"
    INHERITED = "inherited"
    BLOCKED = "blocked"


class ValidationStatus(StrEnum):
    PASS = "pass"
    HOLD = "hold"
    FAIL = "fail"
