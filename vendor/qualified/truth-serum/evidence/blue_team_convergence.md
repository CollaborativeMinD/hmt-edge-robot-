# Blue Team Convergence

Four independent surfaces converged out of band: architecture/contracts, runtime/admission,
implementation/security, and root closeout. Each lane began from the supplied candidate HOLD and
attempted to falsify the repaired state before promotion.

| Surface | Reproduced defect | Closed control |
| --- | --- | --- |
| Architecture | contradictory CLEAR/BLOCKED claims; policy not executable | exact 001..011 trace and loaded closed lane policy |
| Admission | unavailable/malformed witnesses could clear | explicit HOLD/FAIL/ESCALATE routes and strict native JSON |
| Evidence | open/ambiguous claims and stale output reuse | frozen claim model, byte rebinding, fresh runtime output |
| Security | secret and shell-comment bypasses | secret-path/value denial and first-command strict-mode check |
| Integrity | cache-blind seal, unchecked envelope, symlink read-before-check | boundary-first preflight and closed seal envelope |
| Operations | in-repo virtualenv/cache self-corruption | external frozen environment and cache-free SOP commands |

Convergence criterion: all previously good gates were rerun after each repair class; the final
state passed the full regression suite, all mandatory witnesses, Scaffoldctl worktree/index/tree,
Truth Serum CI, seal mutation tests, and clean-room verification.
