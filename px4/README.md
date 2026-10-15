# dawnr ▸ px4 — formal safety-property gates for PX4

A small, self-contained tool that turns a PX4 safety invariant into a **machine-checked, replayable proof**
wired as a regression gate. Each gate proves that a specific PX4 function keeps its contract (an index stays
in-bounds, a clamp stays in range, a swap restores an ordering, a predicate is exact), using dawnr (`t` spec
→ up to seven independent provers, twin-refutation). If a future PX4 change breaks the invariant, the gate's
replay fails. Nothing here changes flight code. Full rationale: `../internal/PX4-FIT-2026-10-14.md`.

## Requirements
`dawnr` on `PATH` plus at least one prover (SPARK/gnatprove or Dafny). Everything runs locally and offline —
`verify` replays with NO model, re-running the prover on this machine.

## CLI
```sh
./dawnr-px4 list                       # the gates
./dawnr-px4 verify                     # replay every cert (no model); non-zero exit if any invariant broke
./dawnr-px4 drift                      # is each modeled PX4 function still byte-identical to when it was reviewed?
./dawnr-px4 mint <gate>                # (re)mint a gate's cert from model.t + twin.t + witness.json
./dawnr-px4 new <gate> <px4-file> <symbol>   # scaffold a gate from a PX4 source function
```
`PX4_ROOT` defaults to `~/Projects/PX4-Autopilot` (override to point `drift`/`new` at your tree).

## Gates (4)

| gate | PX4 function | invariant proved | class | twin refuted at |
|---|---|---|---|---|
| `rc_map_index` | `RCUpdate::getChannelIndex` (rc_update.cpp) | a valid RC-map index ∈ `0..17` (18-wide channel/param arrays) | array-bounds | `ch=19 → 18` |
| `constrain` | `math::constrain` (Limits.hpp) | result ∈ `[lo,hi]`; identity when already in range | saturation | `x=100,lo=0,hi=10` |
| `pwm_minmax` | `MixingOutput::updateParams` (mixer_module.cpp) | `min ≤ max` restored by the swap | invariant-restoration | `mn=10,mx=5` |
| `is_in_range` | `math::isInRange` (Limits.hpp) | predicate is exactly `lo ≤ x ≤ hi` (what `getChannelIndex` trusts) | threshold-decision | `x=100,lo=0,hi=10` |

Each real body verifies under dafny/spark/framac/rocq/fstar (measured); the committed certs use SPARK, which
also produces the grounded refutation of the twin.

## A gate folder
```
<gate>/
  model.t       the real PX4 logic + its safety contract (requires/ensures)
  twin.t        the broken variant this gate must catch (same contract, weakened body)
  witness.json  a grounded counterexample input (the twin violates the contract here)
  source.json   {file, symbol, sha256} — binds the gate to the PX4 function it models
  cert.json     the dawnr paired-observation certificate `verify` replays (no model)
  NOTES.md      the PX4 code ↔ invariant mapping
```

## Add a gate
```sh
./dawnr-px4 new battery_failsafe src/modules/.../foo.cpp SomeClass::decide
#  edit battery_failsafe/model.t  (contract + faithful body)
#       battery_failsafe/twin.t   (the regression to catch)
#       battery_failsafe/witness.json  (a concrete breaking input)
./dawnr-px4 mint battery_failsafe   # proves real, refutes twin, writes cert.json
./dawnr-px4 verify                  # it's now in the suite
```

## Faithfulness (the one real caveat)
dawnr proves the `t` **model**, not the C++ line-for-line. `source.json` records a hash of the modeled PX4
function; `drift` flags when that function changes so you re-review `model.t`. This does not prove the model
matches the code (that's a human review of two tiny snippets) — it makes silent drift impossible to miss.
Integer / bounded-array / saturation / boolean logic is the sweet spot; floating-point reasoning is dawnr's
frontier and only partial today.

## CI
Rename `ci.yml.sample` into a workflow (it runs `dawnr-px4 drift` then `verify`). CI needs `dawnr` + one prover
in the runner — a prebuilt dawnr container is the simplest path (installing seven provers is unnecessary; one
is enough to replay these certs).
