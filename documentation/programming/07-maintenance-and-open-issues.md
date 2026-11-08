# Maintenance and open issues

> November 2026 update: this is a detailed source reference. Start with the [current handbook](PROGRAMMING-HANDBOOK.html). The [owner's successful prototype report](reference/prototype-test-confirmation.html) covers the software branch and both updated Nano versions. The [Hiwonder chapter](09-hiwonder-arm-controller.html) supplies the now-confirmed controller and PC tool, official loading route and development references; the [report and asset note](10-reference-context-and-assets.html) adds subsequent report/dataset evidence. Original dates below identify the earlier review session, not a new deployment test.

This chapter supports maintenance of the **structured implementation** using source and desk evidence at the handover baseline. It separates implemented behavior from proposed work. No issue below is repaired in this comment/documentation pass. See [the evidence record](08-evidence-and-change-record.html) for discrepancies with older documents.

## Symptom-to-source navigation

| Symptom | Source-supported explanation to check | Safe desk investigation |
|---|---|---|
| Move/automation wait never finishes | `ApplicationState.wait_for_position/home` has cancellation checks but no operation deadline; missing/mismatched reports cannot complete it | Inject missing/wrong/stale `POS`, then Stop; inspect generations/request state in snapshots |
| Position is logged but grid does not show reached | Router marks rejected motion reports `accepted=false`; reset/home/offline invalidate position | Trace request → parsed event → `ApplicationState.apply()` → GUI `_handle_event()` |
| Hydroponics values stop updating or display implausible values | Client offline/read error, framing overflow or malformed fields; sensor floats accept `NaN`/infinity without plausibility checks | Feed fragmented/combined `STAT` bytes and malformed/nonfinite fields through parser/client doubles |
| Manual workflow says complete despite missing action | Arm-unavailable policy skips the action and continues; normal return is an operation outcome, not hardware acknowledgement | Inject `HardwareUnavailableError`; inspect notices, command history and `OPERATION_STATE` |
| Pesticide starts without selected grid position | Refactored facade/workflow has no position-required gate here; current legacy does | Reproduce in mocks; inspect `ApplicationController.pesticide()` and `WorkflowService.pesticide()` |
| Arm sequence runs from old position or after long pause | Refactor lacks current legacy's per-group same-coordinate `POS` refresh; gantry inactivity can initiate homing | Compare command history against legacy refresh flow; inject timeout/offline during arm waits |
| Reset takes longer than two seconds | Reset deadline bounds quiescence/barriers; later provider starts can exceed it, including model load and Nano settles | Inject slow `start()` and close/barrier doubles; distinguish total elapsed time from cleanup deadline |
| Camera reports no detection after an inference failure | Hardware vision logs the exception and may save `No detection` or select a candidate accumulated before the failure | Inject a broken/partially yielding model; distinguish inference error from valid zero boxes |
| GUI freeze/race in legacy but not reproduced in simulation | Legacy workers directly access Tk; refactor routes via main-thread event queue | Test refactored queue ordering/fake-widget handling; never import legacy to reproduce it |
| Motors disabled after structured homing fault | Current refactored `errorStop()` explicitly disables drivers; legacy did not | Read/compare C++ and source regression tests; physical fault result is unverified |
| Dose timing differs from the requested duration | Shutoff is cooperative; pH sampling/incomplete serial input delays loop progress and `DOSE_TIME` can change active shared-duration deadlines | Trace `HydroponicsController.update()` and synthetic elapsed-time/command cases; see [04](04-controller-firmware.html) |

Relevant files are linked in [01](01-system-and-code-map.html), with call flows in [02](02-pi-application.html) and [03](03-communications.html). Start from the raw log, parsed event and state snapshot separately: they do not all imply the same accepted/completed action.

## Prioritized programming backlog

Priority orders investigation; it does not authorize a behavior change or physical test.

| Priority | Existing evidence / impact | Next desk work | Later validation dependency |
|---|---|---|---|
| P1 | Refactor lacks current legacy's per-arm-group gantry reconfirmation and pesticide position gate; later legacy change is visible at `b87a4f4` | Capture fixtures for same-coordinate refresh, timeout/failure/cancellation and dose-before-arm ordering; decide desired parity explicitly | Identified Nano/arm, inactivity timing, clearance and full workflow acceptance |
| P1 | Refactored gantry fault disable and edge/debounce behavior differ from legacy; implemented in `677d498` | Review each approach/fault path with simulated switch traces; capture intended acceptance and build metadata | Physical homing/endstop/fault tests and pulse/timing observations |
| P1 | GUI Stop cancels Pi orchestration; blocking Nano movement and sent arm actions continue | Document state transitions and define a versioned stop/completion contract before proposing implementation | Separate physical stop design and fault validation; `O` is home-Y-then-disable |
| P1 | Hydroponics lacks plausibility/water/dose/chemical-interaction safeguards; command validation is not process safety | Define invalid sensor/target/dose fixtures and intended policy; quantify unknown assumptions in requirements | Calibration, output/flow/process evidence and separately approved fault tests |
| P2 | Position/home waits lack deadlines; same-coordinate stale reports have no transaction identity | Define operation-specific timeout/late-response semantics with deterministic fixtures | Captured deployment transcripts and acceptance of recovery behavior |
| P2 | Arm endpoint failure warns/skips/continues and fixed sleeps infer completion | Decide whether workflows should fail, recover or skip; distinguish acknowledgement, duration and outcome in event model | Confirmed controller capabilities, group mappings and actual completion times |
| P2 | Relative moves return from send without `POS` fence; sequential queue order does not imply physical completion | Characterize relative/grid/capture interleaving through synthetic firmware transcripts | Measured command acceptance and movement completion on Nano |
| P2 | Reset provider reopening is not totally bounded; teardown deadline does not guarantee actuator safe state | Inject stuck/slow start/read/stop scenarios; define lifecycle and operator outcomes | Camera/model startup and USB reset/home behavior on identified Pi/controllers |
| P2 | `No detection` also represents caught inference failure | Propose explicit inference outcome separate from class label and demonstrate workflow effect with saved-frame/fake-model fixtures | Comparative vision acceptance on real model/camera before changing automation |
| P2 | Dependency pins/build/flashed identities are incomplete | Capture a sanitized software manifest and approved package sources; avoid guessed board profiles | Pi installation and matched compiler/library/controller acceptance |
| P3 | Wire has no ACK correlation, sequence numbers, retry or duplicate suppression | Design backwards-compatible/versioned protocol fixtures; define duplicate dosing/motion semantics | Coordinated Pi + firmware migration and failure/reconnect checks |
| P3 | Hydro settings reset on controller restart; model provenance and arm file mapping absent | Define desired configuration persistence and asset manifest formats separately from runtime changes | Controller wear/reset policy, model owner and installed arm inventory |
| P3 | Console logs/UI history are not a durable controller event record | Define event retention, timestamps/identity and redaction needs; prove via mock traces | Storage/performance/operator review on Pi if later enabled |

Existing mitigations must be retained while evaluating this work: buffered lines, transport write/lifecycle locks, accepted-position generations, queue/state ordering, worker isolation, reset admission barriers, main-thread UI updates, and mock-only composition. They address programming failure modes, but do not establish physical safety or exact legacy parity.

## Onboarding checklist

- [ ] Read root guidance and the package index; identify the baseline commit and evidence labels.
- [ ] Trace simulation composition through `app.py`, provider interfaces and controller construction.
- [ ] Explain plant number vs GUI index vs Nano coordinate, requested vs reported state, and local generations vs wire identity.
- [ ] Trace one grid movement, one `STAT` record and one action-group frame without opening hardware.
- [ ] Read the manual/automation branches and identify cancellation/completion assumptions.
- [ ] Inspect test isolation before running the standard-library suite; record interpreter/commit/result.
- [ ] Review current structured gantry/hydro source, including all matching `.cpp/.h` files.
- [ ] Recognize historical artifacts and preserve the rollback reference.
- [ ] Read the parity gaps above before proposing deployment or claiming equivalence.

## Handover acceptance checklist

- [ ] The handbook, index and detailed reference chapters exist, links resolve, and major symbols refer to current source.
- [ ] Pi, both Nano firmware projects, communications, vision/assets, mocks, development and recovery are covered.
- [ ] Existing intentional differences, missing evidence and stale historical statements are explicit.
- [ ] Source annotations preserve Python AST/non-comment tokens and C++ non-comment tokens/directives.
- [ ] Verification commands/results are dated; historical operator checks are not presented as rerun.
- [ ] Hardware integration/validation remains pending wherever records are absent.
- [ ] Programming scope and its mechanical/electrical interface limits are clear.

The programming handover can be accepted with accurately recorded evidence gaps. Deployment acceptance requires a different record, with actual hardware identity/state, procedure, expected/observed result, date and operator.
