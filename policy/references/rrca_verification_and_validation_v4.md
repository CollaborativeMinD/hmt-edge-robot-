# Reverse RCA protocol v4

<verification_validation>
- Generate a tracer bullet first before building any full system, plan, or feature, etc., in conjunction with scratch_pad.py and white_board.html. Do not build the full thing before analyzing the tracer bullet(s) until one holds within the needs, boundaries, and legal parameters of the architecture/request/ticket, etc you're tasked with.

- Inside of every new, edited, or handoff package The final `Runbook.md` that goes in the root must be an SOP style doc. And the `Agents.md` is an orchestration and interception interface also at the root. An operator or agent should be able to resolve any and all suspected troubleshooting, views, maintenance requirements, observability commands, bash commands, etc. All V&V'd and satisfy their tagged requirements before acceptance. 
<sub_agent_attestation>
If sub agents are triggered/spawned/called to assist in your task and You are the supervisor, explicitly enforce cross-spectrum contradiction checking. If Agent X generates a brilliant Python function: "For Agent X's telemetry to be legally true, upstream state B had to occur...**[Verify SQLite Outbox State]**...", but Agent Y's structural JSON manifest leaves an empty string field **[Inspects Agent Y's execution surface against instructions and requirements]**..., or Agent A's timestamp metadata registers OOB clock drift, But A’s artifact claims B never admitted that transition ...., you do not look at the code quality, prose authenticity, or handoff objects. You zero in on the systemic coupling crack and immediately provide corrective feedback and recovery verification gates.
Reverse RCA ledger shall contain a maximum of seven columns for single-agent execution. When supervised sub-agents are used, an eighth `sub_agent_task_attestation` column is authorized and required.
</sub_agent_attestation>
</verification_validation>
<reverse_rca>
Build verification and validation is a dynamic constraint. After each task item you complete and upon meeting the requirements of your task, the definition of done, implementation laws, and the task plan ssot documents as provided, you must rerun the verification gates of all previously good states. Utilizing a cumulative gate ledger titled: Cumulative Gate Ledger, with max 7 columns (timestamp, task, gate_id, requirement, status, evidence_ref, evidence_hash/reason. disposition can encode the prescribed controlled terminal vocabulary.) that you will create and export at the end of the session in DuckDB, Polars, or SQLite whichever is the most convenient amd fastest for you to retrieve and inspect.

- If anything is corrupted due to the new algorithms, functions, schemas, etc., you developed for the current task, stop, and go back and fix the couplings before testing and proving its update satisfies the requirements before proceeding. 

- You shall trace the issues and resolve the problems by following my Reverse RCA protocol without widening the scope or overfitting. It starts by evaluating the output and asking the question: "For this output to be true, what cascading effects upstream happened, allowed admission, transferred authority, etc.?"  Not just the surface-level bug that's the output of inner/upstream cascading events that allowed its existence. Continue causal traversal backward from the current output under investigation until reaching a reproducible initiating condition, an immutable external dependency, an explicit architectural boundary, or an evidence-backed environmental limitation. Do not continue speculative traversal beyond the last evidenced causal edge.

- Solve it, then work back down the causal chain via regression testing to ensure the actual event was reproducible and remedied closed. Give every regression gate a stable identity. Something like:

```
G-ARCH-001
G-SCHEMA-002
G-AUTH-003
G-RUNTIME-004
G-REPLAY-005

```

- For all errors, malformations, etc that initiated the reverse rca protocols, document them from start to finish for continuity purposes utilizing a ledger titled: Reverse RCA Ledger, with max 7 (timestamp, incident_id, checkpoint, observed_state, causal_evidence, validation_test, disposition. disposition can encode the prescribed controlled terminal vocabulary) columns you create and export at the end of the session with DuckDB, Polars, or SQLite whichever is convenient for you to retrieve and review, including the initial bug/error/constraint breach and the checkpoints traversed throughout the causal traceroute backward to find the break(s), and what the solution was. Include testing done on the way back down the previously broken chain, a timestamp, and the disposition should include the Investigation State reason code: INVESTIGATION_COMPLETE or INVESTIGATION_INCOMPLETE, and Remediation State reason code: SOLUTION_CANDIDATE_APPLIED or REQUIRES_OPERATOR_ESCALATION (if due to environmental/container/tool limits, architectural drift/clarity, or consequences based in reality, credibility, or increased authority) statuses prescribed to the RCA.
</reverse_rca>