# Evidence interpretation

`baseline_tracer.json` reproduces the inherited controller's false-success defect.
`exploration_receipt.json` cites the scratch/whiteboard proof by source hash and is
EXPLORATION_ONLY. Neither is counted as successful replacement robotics behavior.

Each final validation invocation stores immutable logs and the JUnit receipt under
`evidence/runs/<UTC timestamp>/`. Earlier development ledger entries reference
rolling log paths; their historical log bytes may have been superseded. Those
records are retained as development history, not promoted into final hash-verified
acceptance. The final current-run checks rerun every software gate and requirement
binding. Database/CSV/Parquet exports have seven columns each. RRCA row timestamps
are ledger recording times, not invented original incident occurrence times.

The live session accounts for eight attempted inference requests: two direct
OpenAI rejections, two requests exposing the routed identifier mismatch, and four
requests in the final successful canary. The failed attempts retain full reserved
cost; missing usage is not billed as zero. The final successful run reports
$0.0011476. The sum of full reservation bounds for the complete session is
$0.0191584 against the user-authorized $1 maximum. No paid run is part of normal CI.

The workflow listing connector returned no runs even after Actions had completed;
raw Actions API lookup reconciled the extra launch and all recorded attempts.
Provider metadata checks made no inference requests. OpenAI/Anthropic credentials
were rejected; OpenRouter and Gemini metadata checks passed. OpenRouter was chosen
with OpenAI-only routing, fallback disabled, strict schema support and price caps.

The final canary checked explicit qualification, inspect, diagnose and hold under
a stopped-state injection. Zero driver movements occurred. It establishes a narrow
live integration result, not general accuracy, safety certification, or a model
training/holdout evaluation. Statistical ML and physical deployment gates remain
HOLD. Read `compliance.md` before interpreting software PASS as release authority.


The triad update has a new software evidence series in `evidence/triad/` and current
cumulative gate runs. The earlier `source_manifest.json`, GitHub CI receipt and
archive admission receipts describe their original sealed checkpoints; they are
preserved as historical evidence rather than rewritten to claim the new code.
The triad source manifest binds the new acceptance source independently. Readiness
campaign statistics are empirical. The incomplete file-manifest verdict is required
truth, not a failed software campaign. No hardware or paid inference calls occur.

The Pyrefly update preserves prior robotics and triad source seals. Its initial
diagnostics and independently bound source receipt are in `evidence/types/`. The
current cumulative series adds G-TYPES-012 alongside Ruff and rechecks all software
gates; old successful type-free runs remain historical observations.
