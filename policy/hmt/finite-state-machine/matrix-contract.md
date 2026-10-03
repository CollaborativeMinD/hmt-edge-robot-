# Default PACE Pavlovian Matrix Contract

## Contract summary

`FSM.PACE.DEFAULT.001` provides a reusable reflex spine for digital twins. It is designed to sit downstream of mission-specific pressure calculation and upstream of authority selection.

## Inputs

The evaluator consumes a reduced pressure surface derived from the governing state vector and its coupled formula families:

| Field | Meaning |
|---|---|
| `m_min_now` | Weakest current APS margin. |
| `debt_weighted` | Weighted integrated pressure debt. |
| `rtp` | Recovery time pressure. |
| `tau_ttv` | Timing/hardware trust. |
| `observer_confidence` | Truth/observer confidence. |
| `terminal_pressure` | Fused terminal pressure. |
| `safe_control_exists` | CLF-CBF/HJI says safe control path exists. |
| `energy_latency_margin` | Energy and latency recovery margin. |
| `recovery_margin` | Fused remaining recovery margin. |
| `bounded_disturbance_admitted` | Disturbance admission status. |
| `evidence_hash_valid` | Evidence integrity. |
| `deadman_bound_clear` | Temporal safety bound status. |
| `gcb_zeroized` | Runtime membrane zeroization status. |

## Hard override order

1. State hash invalid -> `TERMINAL`
2. Evidence hash invalid -> `TERMINAL`
3. Disturbance bound exceeded -> `TERMINAL`
4. Deadman bound failed -> `TERMINAL`
5. Terminal pressure saturated -> `TERMINAL`
6. Recovery time pressure closed -> `TERMINAL`
7. Safe-control set empty -> `TERMINAL`
8. Energy-latency margin collapsed -> `TERMINAL`
9. Observer truth collapse -> `EMERGENCY`
10. GCB zeroized -> `EMERGENCY`
11. Disturbance not admitted -> `EMERGENCY`

## Soft threshold matrix

| State | Default condition |
|---|---|
| `PRIMARY` | `m_min_now >= 0.30`, `debt_weighted <= 1.0`, `rtp <= 0.60`, `tau_ttv >= 0.80`, `observer_confidence >= 0.85`, `terminal_pressure <= 0.20` |
| `ALTERNATE` | `m_min_now >= 0.15`, `debt_weighted <= 3.0`, `rtp <= 0.75`, `tau_ttv >= 0.65`, `observer_confidence >= 0.70`, `terminal_pressure <= 0.45` |
| `CONTINGENCY` | `m_min_now >= 0.05`, `debt_weighted <= 6.0`, `rtp <= 0.90`, `tau_ttv >= 0.45`, `observer_confidence >= 0.55`, `terminal_pressure <= 0.75` |
| `EMERGENCY` | Otherwise, when no terminal hard override fires. |

## Hysteresis law

```text
hard_terminal_event -> TERMINAL
hard_emergency_event -> EMERGENCY
soft_demote_count >= 2 within last 3 ticks -> demote one rung
recovery_clear_count >= 5 consecutive ticks -> promote one rung
TERMINAL has no automatic recovery path
```

## Smoke result

The included bounded smoke generated:

```text
PRIMARY, PRIMARY, ALTERNATE, ALTERNATE, CONTINGENCY, CONTINGENCY, EMERGENCY, TERMINAL
```

Transition ticks:

```text
2, 4, 6, 7
```

## APS.EQ.009 / APS.EQ.010 Dissipation Addendum

The reflex spine now includes a deterministic pressure-debt regulator. This fills the gap between APS accumulation and PACE recovery.

### APS.EQ.009 — linear pressure dissipation

```text
sigma(t) = stress(t) / limit(t)
D_dot(t) = sigma(t) - beta, if sigma(t) > beta
D_dot(t) = -rho, if sigma(t) <= beta
D(t + dt) = max(0, D(t) + D_dot(t) * dt)
```

`beta` is the safe band. `rho` is the finite linear dissipation rate. The zero-floor clamp is mandatory: pressure debt cannot become negative.

### APS.EQ.010 — deterministic recovery time

```text
T_rec(t) = D(t) / rho, if D(t) > 0 and rho > 0
T_rec(t) = 0, if D(t) == 0
T_rec(t) = infinity, if D(t) > 0 and rho == 0
```

PACE no longer guesses when recovery can begin. The scheduler can inspect `T_rec` and compute:

```text
RTP = T_rec / TTV
```

When `RTP >= 1.0`, recovery time has closed the terminal horizon and the reflex spine must route to `TERMINAL` unless a higher-priority mission-specific handoff rule is explicitly supplied and evidenced.

### Smoke scenario binding

The bundled smoke uses a sealed thermal sensor package:

```text
limit = 90 C
safe_band beta = 0.70
rho = 0.10 debt/minute
dt = 1 minute
w_max = 1.0
```

The stress path remains disturbance-bounded while thermal debt rises, forcing:

```text
PRIMARY -> ALTERNATE -> CONTINGENCY -> EMERGENCY -> TERMINAL
```

Terminal is caused by `RECOVERY_TIME_PRESSURE_CLOSED`, not by arbitrary hysteresis guessing.
