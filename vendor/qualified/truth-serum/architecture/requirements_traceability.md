# Requirements Traceability

The matrix is the authoritative repository-admission digital thread. Each row
has one requirement, invariant, contextual satisfier, oracle, and evidence route.

| Requirement | Invariant | Satisfied by | Oracle | Required evidence |
| --- | --- | --- | --- | --- |
| REQ-TS-001 | INV-TS-001 | `repositoryAdmission.inventory` | ORACLE-TS-001 | Repository-boundary and stable-order tests |
| REQ-TS-002 | INV-TS-002 | `repositoryAdmission.airlock` | ORACLE-TS-002 | Strict-schema negative tests |
| REQ-TS-003 | INV-TS-003 | `repositoryAdmission.policy` | ORACLE-TS-003 | Mode-to-lane policy tests |
| REQ-TS-004 | INV-TS-004 | `repositoryAdmission.witnesses` | ORACLE-TS-004 | Required-tool-unavailable test |
| REQ-TS-005 | INV-TS-005 | `repositoryAdmission.aggregator` | ORACLE-TS-005 | Finding, error, and terminal tests |
| REQ-TS-006 | INV-TS-006 | `repositoryAdmission.evidence` | ORACLE-TS-006 | Admission-trace schema and replay test |
| REQ-TS-007 | INV-TS-007 | `repositoryAdmission.aggregator` | ORACLE-TS-007 | Repeat-run equivalence test |
| REQ-TS-008 | INV-TS-008 | `repositoryAdmission.airlock` | ORACLE-TS-008 | Namespace compatibility audit |
| REQ-TS-009 | INV-TS-009 | `repositoryAdmission.witnesses` | ORACLE-TS-009 | Source-size and debris guards |
| REQ-TS-010 | INV-TS-010 | `role6_14` | ORACLE-TS-010 | Machine-handoff role assertion |
| REQ-TS-011 | INV-TS-011 | `repositoryAdmission.sealVerifier` | ORACLE-TS-011 | Authority-separation regression test |

## Oracle acceptance rules

- ORACLE-TS-001: attempts to escape the root are rejected; sorted inventory is stable.
- ORACLE-TS-002: unknown fields, invalid enums, and malformed JSON are rejected.
- ORACLE-TS-003: all four modes resolve to declared required and optional lanes.
- ORACLE-TS-004: a required unavailable witness produces `HOLD`, never `PASS`.
- ORACLE-TS-005: blocking evidence produces `FAIL`, untrustworthy execution produces
  `HOLD`, and terminal evidence produces `ESCALATE`.
- ORACLE-TS-006: trace events reconstruct attempt, mode, stages, artifacts, transitions, reasons, and evidence.
- ORACLE-TS-007: equal governed inputs produce equal ordered decision content.
- ORACLE-TS-008: namespace and posture aliases are absent or explicitly mapped.
- ORACLE-TS-009: Python size limits and debris policy pass on the release tree.
- ORACLE-TS-010: handoff identifies `edge_devsecops_iac`, canonically bound to
  slot `6_14`, without elevating its authority.
- ORACLE-TS-011: admission cannot claim target execution, human approval, or create the closeout checksum.

An orphaned cell is a blocking trace defect. Formula and equation identifiers are
`N/A`: this repository contains no executable physical or control law.
