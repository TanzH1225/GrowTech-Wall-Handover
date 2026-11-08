# Known limitations and unresolved risks

> Current-source note (2026-10-09): This record retains historical phase findings. The [2026-10-09 maintenance chapter](../07-maintenance-and-open-issues.html) and [evidence record](../08-evidence-and-change-record.html) distinguish current legacy/refactored behavior, including arm-refresh parity, changed refactored gantry fault handling and caught inference failures. Read those reconciliations alongside the tables below.

## Status labels

- **Verified legacy behavior** means directly evidenced by checked-in source, captured environment, Git history, or an explicitly recorded legacy observation.
- **Desk-verified future work** means new/refactored behavior checked only with source comparison, static checks, mocks, fixtures, or laptop simulation.
- **Unverified physical detail** means the repository is insufficient to establish the real wiring, calibration, device identity, or physical outcome.
- **Deferred improvement** means proposed future work that is neither implemented nor validated.

## Raspberry Pi application

| Severity | Limitation | Status | Consequence / deferred direction |
|---|---|---|---|
| Critical | Full auto waits for `POS` after `0 0`, but gantry home emits no `POS` | Verified legacy behavior from source | Workflow can wait indefinitely; define a backward-compatible homing completion state after protocol capture |
| High | Scan-only homing wait can pass from GUI state instead of a new hardware report | Verified legacy behavior from source | Movement/capture can be coordinated from stale state; future state model must separate requested/reported state |
| High | Automation, capture, and arm workers access Tk objects outside the main thread | Verified legacy behavior from source | Freeze/race/crash risk; future main-thread event queue |
| High | Multiple waits have no deadline or structured failure | Verified legacy behavior from source | Indefinite worker threads; future operation-specific deadlines and cancellation |
| High | Shutdown releases only the camera | Verified legacy behavior from source | Ports/workers/actions are not explicitly closed or stopped; future shutdown state machine |
| Medium | Serial reset sleeps on the GUI thread and races the reader | Verified legacy behavior from source | UI freeze and port errors; future serialized transport lifecycle |
| Medium | Model path and device paths are hard-coded | Verified legacy behavior from source | Machine-specific deployment; future validated configuration file |
| Medium | ONNX fallback receives a `.pt` path | Verified legacy behavior from source | Fallback is not credible; choose and test one backend or a valid ONNX model |
| Medium | GUI often changes desired state before controller confirmation | Verified legacy behavior from source | Display can disagree with hardware; future requested/acknowledged/reported states |

### Parallel Pi rewrite limitations

| Severity | Limitation | Status | Consequence / required validation |
|---|---|---|---|
| High | `Homing complete.` now completes the refactored `0 0` wait; a fresh associated `POS 1 1` is also accepted | Desk-verified future work; intentional correction | Prevents the source-verified legacy indefinite wait in mocks, but the deployed serial transcript and physical zero/alignment must be validated |
| High | An expected arm endpoint failure warns, skips the group, and continues the containing legacy workflow | Desk-verified future work preserving legacy-facing behavior | Continuing without the arm action may leave the physical sequence invalid; prototype acceptance must explicitly approve or reject this policy |
| High | Gantry, Hydroponics, camera, and model failures stop the affected operation and reach a GUI error; failed pesticide dosing stops before arm group 6 | Desk-verified future work | Mock events prove routing, not the endpoint's physical/fault state; disconnect cases require isolated prototype testing |
| High | Scan-only Stop checks the post-capture second in 100-ms slices | Desk-verified future work | Improves Pi orchestration response only; it cannot interrupt Nano motion or an arm action already sent |
| Medium | Hydroponics parsing accepts the validated ten-field legacy prefix plus trailing extension fields | Desk-verified future work | Real deployed fragmented, combined, malformed, and extended records still require transcript comparison |
| Medium | Manual workflow exclusivity and endpoint feedback depend on the Tk event queue | Desk-verified future work | Mock tests and simulation inspection do not establish touchscreen timing or operator usability on the Pi |

## Communication

| Severity | Limitation | Status | Consequence / deferred direction |
|---|---|---|---|
| Critical | GUI Stop cannot interrupt a blocking gantry move or already-started arm action | Verified legacy behavior from source | Stop is orchestration cancellation, not emergency stop; physical stop design is unverified |
| High | No transaction IDs, ACK correlation, retry policy, or duplicate suppression | Verified legacy behavior from source | Lost/duplicated/ambiguous commands; future versioned protocol |
| High | No serial write lock across workers | Verified legacy behavior from source | Potential command interleaving; future per-transport lock/queue |
| High | Hydro reader does not buffer complete lines | Verified legacy behavior from source | Fragmented/combined `STAT` records can be dropped |
| High | USB serial reopen can reset a Nano | Source-supported, physical behavior unverified for deployed bridges | Gantry may home during reconnect; must be characterized physically |
| Medium | Retained udev rule requests an arm alias that is currently absent, while source uses native UART | Verified deployment/configuration/source discrepancy | `/dev/ttyAMA1` is the active source path; do not activate/substitute `/dev/arduino_roboticarm` without investigation |

## Gantry Nano

| Severity | Limitation | Status | Consequence / deferred direction |
|---|---|---|---|
| Critical | `O` homes dual Y before driver disable | Verified legacy behavior from source | It is not an immediate emergency stop |
| High | Normal movement is blocking and cannot parse a stop command | Verified legacy behavior from source | Motion continues until completion/fault |
| High | Inactivity timeout initiates full homing before disable | Verified legacy behavior from source | Unexpected movement after inactivity |
| High | `errorStop()` loops forever without explicit driver disable | Verified legacy behavior from source | Holding/driver state after homing fault requires physical characterization |
| High | Normal moves use software bounds without continuous endstop checks | Verified legacy behavior from source | Incorrect position or mechanical fault may not be detected |
| Medium | Homing bump retraction has no timeout | Verified legacy behavior from source | A driver/mechanical problem may block indefinitely |
| Medium | Driver type, current, mechanics, real speed, and endstop wiring are undocumented | Unverified physical detail | Required before changing speed, acceleration, or homing |

## Hydroponics Nano

| Severity | Limitation | Status | Consequence / deferred direction |
|---|---|---|---|
| Critical | No sensor plausibility/disconnection detection before automatic dosing | Verified absence in source; actual sensor fault response unverified | Invalid input may request chemical dosing |
| Critical | No water-level interlock for chemical dosing | Verified absence in source | Dosing into insufficient water is not prevented in software |
| High | Acid and fertilizer logic can be active concurrently | Verified legacy behavior from source | Chemical interaction risk; physical process requirements unverified |
| High | Dose and target commands lack safe maximums | Verified legacy behavior from source | Excessive durations/targets can be accepted |
| High | `DOSE:PEST:<mL>` ignores the pesticide mL value | Verified legacy behavior from source | Duration follows global `doseTimeMs` instead of command amount |
| High | Water/light persist across Pi communication loss | Verified protocol behavior; hardware output behavior on faults unverified | Loss of supervisor does not imply off |
| Medium | Settings are not persisted | Verified legacy behavior from source | Targets/schedule revert on Nano reset |
| Medium | Calibration utility pins/constants differ from active firmware | Verified repository discrepancy | Calibration provenance and accuracy are unverified |
| Medium | One mL per second dosing assumption is undocumented physically | Unverified physical detail | Actual delivered volume is unknown until measured |

## Vision and robotic arm

| Severity | Limitation | Status | Consequence / deferred direction |
|---|---|---|---|
| High | Model training data, class map, metrics, and physical validation record are absent | Unverified physical detail | Detection meaning/accuracy cannot be independently reproduced |
| Medium | ROI comment and implementation differ: code keeps central two-thirds | Verified legacy behavior from source | Future refactor must preserve code behavior until intentionally validated |
| High | Arm completion is inferred from fixed sleeps with no acknowledgement | Verified legacy behavior from source | Workflow can proceed before/after real completion |
| High | `.rob` deployment-to-group mapping is undocumented | Unverified physical detail | Action group identity cannot be reconstructed confidently |
| High | Inactive arm udev alias differs from the native UART used by source | Verified discrepancy | Legacy prototype groups worked, but any refactored arm control or transport requires new physical validation |

## Deployment and handover

- The current deployment boots from a 116.5 GB SD card, with `/dev/mmcblk0p1` at `/boot/firmware` and `/dev/mmcblk0p2` at `/`. A private full-disk image is recommended for disaster recovery, but no disk image should be committed to Git.
- The verified `tty1` systemd override auto-logs in `growtechwall`. This is console behavior with physical-access implications, not GUI autostart.
- The confirmed operator procedure starts `GTW_GUIv2.py` manually after boot. No automatic GrowTech GUI launcher was discovered in the supplied evidence.
- SSH and Raspberry Pi Connect are enabled/configured, but exact unit configuration, credentials, tokens, host keys, and access restrictions were not captured and must not be committed.
- Gantry and hydro aliases currently resolve to `/dev/ttyUSB1` and `/dev/ttyUSB0`; because rules are topology-based, those underlying tty numbers and identities must be reverified after USB/hub changes.
- A proposed `requirements-pi.txt` exists in the parallel rewrite, but it is not a reproduced lock file and its Bookworm ARM64 pins/wheels remain untested on the real Pi.
- OS/package presence, SD-card layout, console auto-login, manual startup, remote-access enablement, and current serial alias resolutions are captured. Exact camera/display/UART boot settings, desktop/touchscreen configuration, GUI autostart, remote-access details, and most other service/boot configuration remain uncaptured.
- Udev rules are topology-based rather than serial-number-based.
- Firmware board settings, compiler/library versions, flashed hashes, and rollback images are absent.
- Wiring, relay polarity as physically installed, pump flow, chemical concentration, tank volume, calibration dates/solutions, emergency-stop wiring, and arm-controller firmware remain unverified.
- No durable controller event log or signed hardware validation record exists.

These gaps must remain labelled unverified. A future document may upgrade a gap to hardware-validated only when it includes the test setup, procedure, expected and observed result, date, and operator.
