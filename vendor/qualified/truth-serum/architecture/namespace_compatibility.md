# Namespace Compatibility

These starred families are semantic lane namespaces, not reason-code prefixes.
Runtime reason codes are outcome-first (`PASS_*`, `HOLD_*`, `FAIL_*`, or
`ESCALATE_*`). The lane families describe different facts and are not interchangeable.

| Namespace | Meaning | Canonical values |
| --- | --- | --- |
| `EVIDENCE_*` | State of a referenced evidence artifact | `PRESENT`, `MISSING`, `MALFORMED`, `UNWRITABLE` |
| `WITNESS_*` | Result of one bounded witness lane | `PASS`, `FAIL`, `UNAVAILABLE`, `ERROR`, `NOT_APPLICABLE` |
| `ADMISSION_*` | Aggregated repository decision or reason | `PASS`, `HOLD`, `FAIL`, `ESCALATE` |

`OOD` means `OUT_OF_DISTRIBUTION` only. It is contextual vocabulary from the
governing ontology and is not calculated by this repository-admission tool.
`out_of_domain`, `off_distribution`, and similar spellings are not aliases.

The core repository posture dialect is `PRIMARY`, `ALTERNATE`, `CONTINGENCY`, and
`EMERGENCY`. `TERMINAL` is a repository-local fail-closed extension. External
exports must either preserve the extension marker or map it through an approved
interface contract; they may not silently present it as a core P/A/C/E state.

| Decision | Repository posture | Meaning |
| --- | --- | --- |
| `PASS` | `PRIMARY` | All required lanes produced admissible evidence. |
| `HOLD` | `ALTERNATE` | Required evidence or a required witness is unavailable. |
| `FAIL` | `EMERGENCY` | A blocking repository defect was observed. |
| `ESCALATE` | `TERMINAL` | Local authority cannot safely decide or continue. |

Compatibility is semantic, not merely lexical: an evidence file marked `PRESENT`
cannot make its witness `PASS`, and a witness `PASS` cannot grant human acceptance.
