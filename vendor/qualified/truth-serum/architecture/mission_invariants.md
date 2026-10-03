# Mission Invariants

| Invariant | Repository-admission law | Observable denial |
| --- | --- | --- |
| INV-TS-001 | Reads and writes remain under the selected repository root; inventory order is stable. | `ESCALATE_REPOSITORY_SYMLINK_ESCAPE` or boundary-test failure |
| INV-TS-002 | Boundary payloads reject unknown fields, invalid enums, and malformed values. | Contract error, exit 2 |
| INV-TS-003 | Every requested mode resolves through the versioned lane policy. | Policy contract test failure |
| INV-TS-004 | Missing required witnesses produce `HOLD`; absence is never evidence of quality. | `HOLD_WITNESS_<TOOL>_UNAVAILABLE` |
| INV-TS-005 | Blocking findings produce `FAIL`; untrustworthy witness execution produces `HOLD`; terminal conditions produce `ESCALATE`. | `FAIL_WITNESS_<TOOL>_FINDING`, `HOLD_WITNESS_<TOOL>_ERROR`, or `ESCALATE_SECRET_EXPOSURE` |
| INV-TS-006 | Each attempt is reconstructable without relying on console history. | Admission-trace replay failure |
| INV-TS-007 | Equal governed inputs produce equal decisions and reason ordering. | Repeat-run equivalence failure |
| INV-TS-008 | Evidence, admission, and witness vocabularies never substitute for one another. | Namespace compatibility audit failure |
| INV-TS-009 | Production Python functions are at most 60 source lines, modules are below 100 lines, and debris is absent. | `FAIL_SOURCE_FUNCTION_APERTURE`, `FAIL_SOURCE_MODULE_APERTURE`, or `FAIL_REPOSITORY_SHAPE` |
| INV-TS-010 | Team slot `6_14` owns specialist execution but cannot transfer architecture, audit, or human authority. | Machine-handoff schema failure |
| INV-TS-011 | Runtime admission, closeout checksum, target activation, and human acceptance remain distinct. | Authority-separation regression failure |

## Preservation rule

Any repair that changes an input, contract, policy, stage, reason, or evidence route
must rerun the oracle for that row and every previously passing oracle. A surfaced
failure is traced backward from output to admission, authority transfer, and source,
then replayed forward through the affected regression chain.
