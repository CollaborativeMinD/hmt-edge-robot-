# HMT Model Roles, Convergence, Embodied Specialist, and Local Model Viability Policy v1.2.0

**Policy ID:** `HMT-MODEL-ROLES-CONVERGENCE`  
**Status:** `CANDIDATE_FOR_HUMAN_ARCHITECT_PROMOTION`  
**Issued:** 2026-09-08T23:26:27Z  
**Authority:** Human Architect only  
**Supersedes after promotion:** v1.1.0

## Decision

The existing role separation remains unchanged: LFM proposes orchestration, Granite performs task-scoped semantic review, deterministic code applies controlled dispositions, Chronos-2/Toto provide bounded forecasting, NetworkX plus DuckDB remain the classical graph core, and Qwen-Drive-1.0-4B remains the revision-pinned **embodied multimodal SHADOW specialist**. v1.2.0 adds a local-model viability and model-reselection precedence law: model-dependent roles must first prove a viable <=32B local path, and qualification failure triggers bounded SRR plus same-model reevaluation before model reselection. It adds no general MCP tool and grants no effect authority.

## Frozen references

| Artifact | SHA-256 |
|---|---|
| `HMT_Model_Roles_and_Convergence_Policy_v1.0.0.json` | `ae4b024108a32717a5c2d93e0aa6f497bb5aaeb4c1cf186bbca002af1fe3afe1` |
| `HMT_Baseline_MCP_Tools_v1.2.0.json` | `7b0d96e40ba3b678c7b2c463063052dd61a8781c97f2231a8b76de10fbf22be8` |
| `HMT_Axioms_Policy_v1.0.0.json` | `a32f92ab9c090c25a8d19e5a8e17dd97ecb289ab1aab7f29c216b4f2bba982da` |
| `HMT_rrca_policy_v4.json` | `dd20bbcf45cf1c1a9767df0a98b854d8ca3b0958c58336809162de53645c57af` |
| `HMT_Model_Roles_and_Convergence_Policy_v1.1.0.json` | `f5cd552c667fd9acf893215b493e1b88c8bba2f8cbd984d0769c1c8e854f69bc` |

## Qwen-Drive upstream lock

| Item | Frozen value |
|---|---|
| Model | `Qwen/Qwen-Drive-1.0-4B` |
| Model revision | `28484089a7cc8c335cf5089fb0745cf7c49b6eaa` |
| Source | `QwenLM/Qwen-Drive-1.0` |
| Source revision | `28091c1532e869bc7aee91fc0aef6b3e6fd0b2e0` |
| License | Apache-2.0 |
| Shared VLM | Qwen3.5-4B |
| Upstream runtime | Python 3.12, CUDA 12.8, 24 GiB or greater GPU recommended |

## Role and authority

`embodied_multimodal_driving_specialist` may perform driving VQA, emit explicit BEV perception, generate candidate trajectories, and provide evidence for replay. It is forbidden from calling actuators, controlling a live vehicle, mutating task or authority state, granting completion, admitting training data, self-promoting, or overriding GCB, Semantic Overwatch, the digital twin, or deterministic command-seam gates.

**Authority ceiling:** `shadow_advisory_perception_and_trajectory_only`.

Capability never mints authority. Model replacement never changes agent identity, role identity, authority, or evidence law.

## Local model viability and reselection law

**Policy rule:** every model-dependent HMT system or specialist role must be embeddable with, or have admitted local access to, a model with a **total parameter count of 32B or less** and must satisfy its role-specific qualification gates coherently, consistently, predictably, and within the declared resource envelope.

For this policy, **local** means inference executes on admitted organization-controlled hardware without depending on a remote model provider for that bounded role. The 32B ceiling applies to total parameter count by default. For MoE models, active parameter count is useful resource evidence but **does not substitute for total model size**. Quantization changes memory footprint, not parameter count.

No universal quality score is invented here. Coherence, consistency, predictability, and requirement satisfaction are judged against the role's admitted requirements, acceptance tests, negative paths, latency/resource ceilings, and evidence contracts.

### Failure transition and SRR precedence

A failed local-model viability or role-qualification gate does **not** immediately authorize a larger or remote model. The required sequence is:

```text
selected model fails local viability or role qualification
  -> SYSTEM REQUIREMENTS REVIEW
  -> inspect/refine only evidence-backed system and role boundaries
  -> reevaluate the same selected model against the refined requirements
  -> authorize model reselection only if the failure remains reproducible
     and is attributable to model capability or deployment fit
```

The bounded SRR must review at least: role breadth, task decomposition, context requirements, memory and retrieval, tool surface, authority boundaries, output contract, deterministic support, supervision, and resource assumptions.

Model reselection is authorized only when all of the following hold:

1. SRR is complete.
2. The refined system or role remains valid against mission and architecture requirements.
3. The same selected model has been requalified against the refined requirements.
4. The failure remains reproducible.
5. Evidence attributes the remaining failure to model capability or deployment fit rather than unresolved architecture debt.

**Prohibited shortcuts:** model reselection as the first response to an unreviewed system failure; using a cloud or oversized model as an architecture patch; claiming MoE compliance from active parameter count alone; silently widening scope to make a model pass; or widening authority during SRR or model reselection.

### Controlled reason codes

| Reason code | Meaning |
|---|---|
| `LOCAL_MODEL_VIABILITY_PASS` | Role passed the admitted local-model viability gate. |
| `HOLD_LOCAL_MODEL_VIABILITY_FAILED` | Local-model viability or role qualification failed. |
| `SRR_REQUIRED_BEFORE_MODEL_RESELECTION` | System Requirements Review is mandatory before reselection. |
| `MODEL_REEVALUATION_REQUIRED_AFTER_SRR` | Re-run the same selected model after SRR/refinement. |
| `MODEL_RESELECTION_AUTHORIZED` | Evidence-backed reselection conditions are satisfied. |
| `MODEL_RESELECTION_NOT_JUSTIFIED` | Reselection is blocked because architecture/role debt or incomplete review remains. |

### Qualification gate extension

The general tracer qualification set now also requires:

- `local_model_viability_32b_total_parameter_ceiling`
- `srr_before_model_reselection`
- `same_model_requalification_after_srr`

Required viability evidence includes total parameter count; active parameter count when MoE; deployed weight bytes; KV-cache requirement at admitted context; peak VRAM and RAM; accelerator requirements; latency distribution; and the declared power/resource ceiling.

**Authority impact:** `NONE`. This law changes model-selection precedence, not model, tool, task, completion, or actuator authority.


## Mode law

| Mode | Attached head | Permitted result |
|---|---|---|
| VQA | none | Advisory text and reasoning evidence |
| BEV perception | `perception` | Observation evidence only |
| Direct planning | `planner-sft` | Candidate trajectory only |
| Reasoning planning | `planner-sft` | Candidate reasoning and trajectory |
| Reasoning planning, reward optimized | `planner-rl` | Candidate reasoning and trajectory only |

`planner-rl` is not admitted for direct planning. The trajectory contract is `N × 50 × 3`, representing `(x metres, y metres, heading radians)` over five seconds at 10 Hz.


## Upstream integration constraints

- The official reference environment is Python 3.12, CUDA 12.8, bfloat16, with 24 GiB or more GPU memory recommended.
- The generic upstream demo can invoke direct planning with whichever planner is attached, while the upstream README restricts `planner-rl` to reasoning-conditioned use. HMT therefore enforces the stricter mode law: `planner-sft` for direct or reasoning planning, and `planner-rl` for reasoning planning only.
- The released BEV perception weights cover fixed 6- or 8-camera surround rigs at 896×512. Forklift camera geometry, calibration, indoor lighting, load occlusion, kinematics, and health telemetry are a new domain and remain `HOLD_UNQUALIFIED_TRANSFER`.
- The perception path compiles two CUDA extensions on first use, so runtime qualification requires a matching NVCC/PyTorch toolchain.

## Required crossing

```text
sensors / recorded scene
  -> revision-pinned Qwen-Drive mode
  -> typed perception, text, or trajectory packet
  -> Semantic Overwatch cross-channel witness
  -> GraphBrain evidence projection
  -> digital-twin and hardware-state comparison
  -> GCB admission
  -> MCP+ effect check
  -> deterministic command seam
  -> SHADOW receipt or BLOCK
```

The model output remains advisory even when every learned channel agrees. Any physical effect requires separately promoted deterministic authority outside the model.

## Qualification ladder

1. Offline static integrity and full SHA-256 verification.
2. Offline VQA, perception, direct-planning, and reasoning-planning tracer execution.
3. Recorded-data replay with golden and negative cases.
4. Live telemetry in SHADOW with no actuator connection.
5. Digital-twin closed-loop campaigns.
6. Hardware-in-the-loop SHADOW campaigns.
7. Controlled closed-course supervised campaigns.
8. Separate Human Architect promotion.

A later stage cannot retroactively satisfy an earlier missing gate.

## Semantic Overwatch requirements

Every run must preserve independently addressable text, BEV, and trajectory outputs. Semantic Overwatch must be able to detect and receipt inconsistency among stated intent, perceived geometry, candidate motion, twin state, and observed hardware state. A single scalar confidence score cannot erase channel-specific residuals or reason codes.

## Descendant and fine-tuning law

A fine-tuned, distilled, quantized, adapter-based, or otherwise modified descendant receives a new model identity. It inherits no authority and re-enters at `SHADOW`. Training may use only admitted, content-addressed evidence. Raw production exhaust and evaluation-fixture leakage are prohibited. Every descendant repeats full integrity, output-contract, semantic consistency, twin, HIL, regression, resource, and negative-path qualification.

## Current disposition

| Gate | Disposition |
|---|---|
| Official metadata, license, revisions, and critical remote LFS hashes | PASS |
| Local full model-byte safeguard | HOLD, execution environment has no permitted external binary pull path |
| Local inference | HOLD, no CUDA device and less than upstream-recommended GPU memory |
| Hugging Face Jobs inference | HOLD, service returned HTTP 402 before job admission |
| Official benchmark numbers | Source-reported; not independently reproduced here |
| Local-model viability policy integration | PASS, static policy validation; model-specific runtime qualification remains unchanged |
| Live effect authority | PROHIBITED |

**Overall:** `CANDIDATE_SHADOW_HOLD_RUNTIME_AND_BYTE_SAFEGUARD`.

This policy becomes effective only after explicit Human Architect promotion. It does not modify the frozen 13-tool MCP v1.2.0 surface.
