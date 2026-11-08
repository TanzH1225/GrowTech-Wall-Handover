# Refactoring status

> Current-source note (2026-10-09): The phase entries below retain their original July evidence/status wording. The [2026-10-09 programming handover](../README.html) records current tracked implementation status, 89 fresh headless tests, later reset/gantry changes and legacy/refactor parity gaps. See its [reconciliation record](../08-evidence-and-change-record.html) before treating an old uncommitted/deferred/compatibility claim as current.

## Status model

| Label | Meaning |
|---|---|
| Verified legacy behavior | Directly evidenced by legacy source, captured environment, Git history, or an explicitly recorded legacy observation |
| Desk-verified future work | New/refactored behavior checked by review, static/text checks, mocks, fixtures, or laptop tests only |
| Hardware-validated future work | New/refactored behavior tested on identified physical hardware with a recorded procedure and result |
| Deferred improvement | Proposed work that has not been implemented and validated |

Source verification is not the same as physical validation. Firmware compilation is desk verification. A GUI mock test is desk verification. Neither permits a hardware-validated label.

## Current baseline

- Working branch: `refactor/gui-architecture`.
- Physically operational legacy reference: existing `main` branch and deployed system, as stated by the project owner.
- Verified Pi boot medium: 116.5 GB SD card `/dev/mmcblk0`, with `/dev/mmcblk0p1` at `/boot/firmware` and `/dev/mmcblk0p2` at `/`.
- Verified console behavior: `growtechwall` auto-login on `tty1` through `/etc/systemd/system/getty@tty1.service.d/autologin.conf`.
- Verified operator procedure: manual GUI startup after boot; console auto-login is not evidence of GUI autostart, and no automatic GrowTech GUI launcher was discovered.
- Verified remote access: SSH and Raspberry Pi Connect are enabled/configured; secret/authentication details remain outside documentation.
- Verified serial paths: gantry `/dev/arduino_gantry` → `/dev/ttyUSB1`, hydroponics `/dev/arduino_hydroponic` → `/dev/ttyUSB0`, and robotic arm through native UART `/dev/ttyAMA1`.
- Verified inactive alias: `/dev/arduino_roboticarm` is currently absent and must not be treated as active.
- Pi entry point preserved: `Raspberry Pi/GUI/GTW_GUIv2.py`.
- Gantry baseline preserved: `gantry_main/`.
- Hydroponics baseline preserved: `NFT_Hydroponics/NFT_Hydroponics_main_copy_20250609193150/`.
- Root `NFT_Hydroponics/NFT_Hydroponics.ino` preserved as historical firmware.
- Model behavior preserved: active source continues to select `bestv5.pt`.

The repository audit itself did not run the deployed system, so its detailed findings are source-verified rather than newly hardware-validated.

## Phase status

| Phase | Scope | Current status | Validation level | Merge gate |
|---|---|---|---|---|
| 0 | Legacy repository and environment audit | Complete | Source/text verified; no hardware execution | Audit review |
| 1 | Baseline preservation, handover documentation, root guidance, conservative `.gitignore`, environment-file rename | Implemented in working tree on 2026-07-17; pending user review; not committed | Desk/text verified only | Review diff and approve documentation |
| 1B | Reconcile verified Pi storage/boot, console auto-login, and manual operator-startup evidence | Implemented in the same uncommitted working tree on 2026-07-17; pending user review | Supplied legacy deployment evidence reconciled; documentation checked on desk only; no Pi configuration changed | Review Phase 1/1B diff |
| 1C | Final deployment manifest and reconciliation of active aliases, native arm UART, remote access, and launcher status | Implemented in the same uncommitted working tree on 2026-07-17; baseline-commit ready pending user review; not committed | Supplied legacy deployment evidence reconciled; Markdown/text/Git checks only; no live Pi access | Review complete Phase 1/1B/1C file set |
| 2A | Parallel Pi/firmware architecture, protocol parsers, mocks, simulation, and proposed requirements | Implemented in uncommitted parallel paths; not deployed | Desk-verified future work only | Compatibility review plus laptop tests |
| 2B | Strict legacy compatibility and deployment-readiness review | Completed as a read-only review; deployment blockers identified | Static/source comparison and laptop-safe tests only | Correct blockers without changing protected legacy paths |
| 2C | Pi operator-compatibility corrections: legacy GUI interactions, visible endpoint failures, homing completion, responsive Stop, and compatible Hydroponics parsing | Implemented in the uncommitted Pi refactor; Windows operator review complete; not deployed | Desk-verified future work plus completed Windows laptop simulation; no hardware test | Commit the reviewed Phase 2 change set, then use separately authorized Pi/prototype validation gates |
| 2C.1 | Reproducible Windows simulation environment and real Tcl/Tk validation | Automated and operator-confirmed manual Windows laptop simulation complete on 2026-07-18; not deployed | Python 3.11.9, Tcl/Tk 8.6, 87 unit tests, focused import/platform-safety checks, in-memory compilation, real-Tk smoke checks, and operator GUI inspection | Phase 2C commit readiness; Pi software integration and prototype validation remain separate pending gates |
| 2C.2 | Phase 2C validation closeout and commit-readiness audit | Complete in the working tree on 2026-07-18; commit-ready; not committed | 87 unit tests, 22 focused safety tests, 47-file compilation, Git/text checks, protected-path audit, and artifact review; no hardware access | Commit the reviewed Phase 2 change set; do not deploy before later authorized gates |
| 3 | Centralized Pi configuration while retaining `GTW_GUIv2.py` entry point | Deferred improvement | None | Desk tests and controlled Pi startup validation |
| 4 | Isolated serial transports with unchanged wire formats | Deferred improvement | None | Mock tests, serial transcript comparison, safe hardware round trips |
| 5 | Isolated vision/camera/model/image-store layer | Deferred improvement | None | Prerecorded-image comparison and controlled Pi camera/model tests |
| 6 | Separate GUI state and automation services; main-thread UI updates | Deferred improvement | None | Mock workflows and full controlled dry run |
| 7 | Internal firmware modularization without pin/protocol/timing change | Deferred improvement | None | Reproducible compilation, bench checks, controlled physical validation |
| 8 | Intentional safety changes: ACKs, stop behavior, validation, dosing interlocks | Deferred improvement | None | Separately approved fault-injection and hardware validation |

## Phase 1 change boundary

Phase 1 is software-only and is limited to:

- renaming the captured environment baseline to remove duplicate `.txt`;
- adding `AGENTS.md`;
- adding documentation under `docs/`;
- adding `docs/pi-deployment-manifest.md` as the consolidated replacement-Pi artifact/configuration index;
- adding a conservative `.gitignore`.

Phase 1B updates those same uncommitted guidance/handover records with verified deployment evidence for the SD-card layout, `tty1` console auto-login, and manual GUI startup. It also ignores private Pi disk-image formats to reduce the risk of committing a disaster-recovery image. It does not create an image or modify the live Pi.

Phase 1C reconciles enabled SSH/Raspberry Pi Connect, the absence of an automatic GrowTech launcher, active Gantry/Hydroponics USB alias resolutions, the native-UART arm path, the inactive arm udev alias, and remaining boot/hardware uncertainties. “Baseline-commit ready” means the requested documentation checks pass; it does not mean committed, deployed, or physically revalidated.

Phase 1 does not edit, import, execute, or upload:

- `Raspberry Pi/GUI/GTW_GUIv2.py`;
- `Raspberry Pi/GUI/ServoControl.py`;
- `gantry_main/`;
- `NFT_Hydroponics/`.

It does not open live camera, GPIO, serial, relay, pump, motor, arm, or Arduino interfaces. No physical validation is claimed.

## Phase 2C correction boundary

Phase 2C changes only the parallel Raspberry Pi implementation, its laptop tests, and future-work documentation. It restores the modal Auto choice with separate Scan Only and Full Auto buttons; stepped Hydroponics setting/dose popups; optimistic water/light button feedback; reset and endpoint dialogs; and visible control disablement during exclusive manual workflows. It preserves the improved buffered framing, stale Gantry report rejection, event ordering, bounded teardown, simulation isolation, and corrected `.pt` model-loading path.

The intentional homing correction accepts `Homing complete.` without waiting for a nonexistent `POS`, while retaining the fresh legacy-expected `POS 1 1` completion path. The scan-only post-capture delay checks Stop every 100 ms. Expected arm endpoint failures warn, skip the group, and continue as the legacy `ServoControl.py` did; Gantry, Hydroponics, camera, and model failures stop the affected operation and are shown through the GUI. A failed pesticide dose stops before arm group 6.

All of these claims are desk-verified future work. No Pi software integration, camera/model test, serial exchange, actuator operation, firmware compile/upload, or physical validation occurred. The protected legacy Pi source, firmware, models, calibration sources, arm action files, and refactored firmware remain unchanged in this correction phase.

## Phase 2C.1 Windows simulation environment and operator validation

The dedicated environment is outside the repository at `..\growtechwall-venv` and was created with the verified `python` runtime. It contains Python 3.11.9, pip 26.1.2, and setuptools 65.5.0. `requirements-dev.txt` is intentionally dependency-free, so no serial, camera, model, GPIO, Arduino, or Pi package was installed. `requirements-pi.txt` was not installed.

Automated laptop validation passed 87 standard-library unit tests, a focused 22-test import/platform/GUI/simulation subset, and in-memory compilation of 47 Python files. Real Tcl/Tk 8.6 smoke runs constructed the simulation GUI and verified the four-tab interface, popup construction, visible workflow-lock lifecycle, and A+B/Acid indicator on/off lifecycle while Water and Light remained independent.

Two accommodations are simulation-only. First, mock exclusive workflows can finish inside one GUI poll, so the GUI retains the visible manual-control lock for at least 400 ms only when `controller.simulation` is true; hardware mode takes the immediate-release branch and receives no added wait. Second, the mock Hydroponics provider publishes timed A+B and Acid `STAT` states so their indicators remain observable for the source-compatible manual-dose duration. That timer is owned only by `simulation/controllers.py`; the hardware serial client, commands, and controller/firmware timing are unchanged.

The operator subsequently confirmed all four tabs; separate Scan Only and Full Auto actions; visible locking for Pesticide, Harvest, and Transplant; Hydroponics popups; Water and Light toggles; both A and B indicators during A+B dosing; the Acid indicator during Acid dosing; Reset Serial completion feedback; visible errors for Capture or Harvest without a selected position; clean close; and the legacy-compatible green Gantry & Arm grid with a visibly distinct selection.

This is completed Windows laptop simulation validation only. Raspberry Pi software integration remains pending, and prototype/hardware validation remains pending as a later separately authorized gate. No camera, serial port, GPIO, Arduino, Raspberry Pi, model runtime, motor, pump, relay, or robotic-arm hardware was accessed by these checks.

## Preservation gates for future phases

Before a behavior-preserving refactor:

1. Capture inputs/outputs for the boundary using mocks or approved legacy transcripts.
2. Identify protected constants, paths, pins, timings, commands, responses, model behavior, and reset behavior.
3. Make one reversible change with a defined rollback.
4. Complete desk verification and label it accurately.
5. Complete any required physical test and record hardware identity, setup, procedure, expected result, observed result, date, and operator.
6. Merge to `main` only after the required physical gate passes.

## Deferred improvements—not current facts

The following remain proposed target behaviors, not descriptions of the current system:

- explicit requested/acknowledged/active/completed/failed state;
- bounded waits and operation-specific cancellation;
- a versioned protocol with acknowledgements;
- a physically validated emergency stop;
- sensor plausibility, water, dose, and chemical-interaction safeguards;
- reproducible Pi and Arduino build/deployment manifests.

These items must not be described as implemented, desk-verified, or hardware-validated until the corresponding evidence exists.
