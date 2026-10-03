# Interfaces

## Command boundary

The operator supplies a local repository path, one supported mode, an evidence
directory under that repository, and an optional deterministic attempt ID. The
process returns exit status and strict JSON artifacts. It never follows a path
outside the selected root or treats a third-party tool as admission authority.

| Input | Contract |
| --- | --- |
| `repo` | Existing local directory; canonicalized before use |
| `mode` | `architecture-only`, `ci`, `post-build`, or `rainy-day` |
| `out` | Repository-relative evidence directory |
| `attempt_id` | Caller value or deterministic `local-<mode>` default |

## Witness boundary

Each adapter shall invoke an argument-vector command with a bounded timeout,
capture stdout and stderr, validate native output, and normalize it to `lane_result`.
`UNAVAILABLE`, `ERROR`, and malformed output remain visible. A witness proposes
facts; the aggregator applies policy and owns the admission decision.

The runtime loads the closed `contracts/lane_policy.yaml` contract for each mode. Any drift or
malformation fails the architecture lane, and external witnesses remain required by default.

## Artifact boundary

`admission_report.json` is the aggregate result. `admission_trace.jsonl` records
ordered stage events. Lane evidence remains repository-relative. The machine
handoff uses the supplied ontology handoff shape. Runtime artifacts never create
or overwrite the final repository closeout checksum.

## Exit contract

| Decision | Exit | Operator action |
| --- | ---: | --- |
| `PASS` | 0 | Review evidence and continue to independent closeout. |
| `HOLD` | 3 | Restore required witnesses or evidence, then rerun. |
| `FAIL` | 1 | Repair the causal defect, then rerun prior gates. |
| `ESCALATE` | 4 | Stop; route the authority or terminal condition. |
| Contract error before admission | 2 | Correct invocation or payload. |
