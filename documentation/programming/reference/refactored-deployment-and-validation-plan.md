# Refactored deployment and prototype-validation plan

## Status and safety boundary

The parallel rewrite is a **desk-verified future implementation** until the recorded physical-validation sequence in this document has been completed on the GrowTech Wall prototype. Source review, laptop tests, simulation, and firmware compilation do not establish physical behavior.

This document is a future deployment procedure. No Raspberry Pi configuration, udev rule, service, camera, serial device, Arduino, relay, pump, motor, or arm controller was accessed or changed while preparing the rewrite.

The legacy application and firmware remain the rollback baseline:

- `Raspberry Pi/GUI/GTW_GUIv2.py` and `Raspberry Pi/GUI/ServoControl.py`;
- `gantry_main/`;
- `NFT_Hydroponics/NFT_Hydroponics_main_copy_20250609193150/`;
- the existing model, calibration, and `Arm Action File/` assets.

Do not begin physical validation without an authorized operator, an agreed safe-state procedure, a clear work area, actuator and chemical isolation appropriate to the step, and a second person able to remove power. The GUI Stop control is orchestration cancellation; it is not a verified emergency stop.

## Pre-deployment evidence gate

Record all of the following before changing the prototype:

1. Repository commit, branch, and worktree status.
2. Raspberry Pi identity, SD-card identity and layout, OS/Python versions, and the active virtual-environment freeze.
3. The SHA-256 of `Raspberry Pi/GUI/bestv5.pt` and the refactored source tree.
4. `readlink -f` and `udevadm info` evidence for the intended Gantry and Hydroponics Nano devices, with actuator power isolated.
5. Existing Gantry and Hydroponics firmware source/hash, Arduino board FQBN, bootloader/processor option, port identity, compiler version, library versions, and successful rollback method.
6. Controller wiring, power domains, installed endstop polarity, relay/load isolation, safe substitute-fluid arrangement, and operator-approved stop/recovery method.
7. Robotic-arm controller identity, native-UART configuration, deployed action-group mapping, clearance envelope, fixtures, and power-removal procedure.

Items 5 through 7 are not fully present in the repository today. Missing evidence is a blocking validation gap, not permission to guess a board setting, wire, calibration, or arm action.

## Laptop desk verification

From the refactored application directory on Windows or another laptop:

```powershell
cd "Raspberry Pi/GUI/refactored"
python -m unittest discover -s tests -v
python app.py --simulate
```

The test command is headless and uses the standard-library test runner. The simulation command displays the recognizable four-tab GUI but must use only mock Gantry, Hydroponics, arm, and vision providers. Confirm from logs that simulation mode was selected. Do not accept a simulation implementation that imports or opens pyserial, OpenCV camera capture, Ultralytics, Pi GPIO, or native UART.

For the Phase 2C operator-compatibility check, inspect all four tabs and record that:

- Auto opens separate **Scan Only** and **Full Auto** buttons;
- manual controls visibly disable during Transplant, Pesticide, Harvest, and Serial Reset;
- Hydroponics schedule, automatic dose, EC, pH, fertilizer, and acid controls use stepped legacy-style popups;
- water/light controls update on the operator request and reconcile to simulated `STAT` state;
- endpoint errors use visible dialogs, the arm compatibility skip uses a visible warning, and reset completion uses the legacy information dialog;
- Stop during the scan-only post-capture interval reaches `stopped` before the full one-second delay.

The headless suite covers these routes with mocks, including `Homing complete.` without `POS`, optional legacy-expected `POS 1 1`, a trailing-field Hydroponics record, and selected endpoint failures. GUI inspection confirms widget presence and interaction shape only.

Passing these checks is desk verification only.

### Phase 2C.1 Windows environment record

The 2026-07-18 Windows simulation environment is intentionally outside the repository:

```powershell
& "..\growtechwall-venv\Scripts\Activate.ps1"
cd ".\source code\Raspberry Pi\GUI\refactored"
python -m unittest discover -s tests -q
python app.py --simulate
```

It was created with Python 3.11.9 from `python`. Tcl/Tk 8.6 is functional. The only installed environment packages are pip 26.1.2 and setuptools 65.5.0; `requirements-dev.txt` requires no third-party packages. `requirements-pi.txt` and all serial, camera, model, GPIO, and Pi-only packages remain uninstalled.

Automated laptop results are: 87 unit tests passed, a focused 22-test import/platform/GUI/simulation subset passed, 47 Python files compiled in memory, and real simulation-only Tk checks passed. The Tk checks covered the four tabs, separate Scan Only/Full Auto controls, the six Hydroponics popups, the visible workflow-lock lifecycle, and A+B/Acid indicator activation and completion while Water and Light remained correct.

Because mock exclusive workflows can finish inside one GUI poll, simulation retains the visible manual-control lock for at least 400 ms. The scheduling branch is guarded by `controller.simulation`; hardware mode immediately releases the GUI lock and receives no added delay. The mock Hydroponics controller also schedules source-compatible A+B/Acid active-status intervals so the indicators are human-observable. Only the simulation provider owns this scheduler; hardware-mode commands and controller/firmware timing are unchanged. The long-running GUI was launched only as `python app.py --simulate`.

The operator confirmed the following manual Windows simulation results on 2026-07-18:

- all four tabs passed;
- separate Scan Only and Full Auto actions passed;
- visible Pesticide, Harvest, and Transplant control locking passed;
- Hydroponics popups passed;
- Water and Light toggles passed;
- A+B dosing visibly activated both A and B top-bar indicators;
- Acid dosing visibly activated the Acid top-bar indicator;
- Reset Serial completion feedback passed;
- Capture and Harvest without a selected position produced visible errors;
- clean application close passed; and
- every Gantry & Arm position button was green initially, with a visibly distinct selected position.

This completes Windows laptop simulation validation only. It does not complete Raspberry Pi software integration or prototype validation; both remain pending and require later, separately authorized procedures. No Raspberry Pi, camera, serial port, GPIO, Arduino, model runtime, motor, pump, relay, or robotic-arm hardware was accessed.

## Exact Raspberry Pi deployment procedure

The current Pi boots from the 116.5 GB SD card at `/dev/mmcblk0`, uses console auto-login, and starts the legacy GUI manually. The refactored application retains manual startup; this procedure does not create or edit an autostart entry, udev rule, service, boot overlay, or UART setting.

1. Preserve a private, access-controlled full image of the known-good SD card for disaster recovery. Never add that image to Git.
2. Obtain the reviewed repository revision at the existing path. The exact approved 40-character commit SHA is a required deployment handoff input; do not substitute the branch tip. If network fetch is approved and required, fetch it first. Then check out and verify that exact commit:

   ```bash
   set -eu
   cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall"
   APPROVED_COMMIT="<approved-40-character-commit-sha>"
   test "$APPROVED_COMMIT" != "<approved-40-character-commit-sha>"
   git status --short --branch
   test -z "$(git status --porcelain)"
   git checkout --detach "$APPROVED_COMMIT"
   test "$(git rev-parse HEAD)" = "$APPROVED_COMMIT"
   ```

   Stop if the approved SHA has not been supplied, the worktree is not clean, checkout fails, or the equality check fails.

3. Verify that the active model still exists at the preserved legacy path:

   ```bash
   sha256sum "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/bestv5.pt"
   ```

   The audit-time expected hash is `87c36a815ee6a0efdde2bc71bec5b6cb1b8855a4958646df56f4afdc8ef9f19`. A matching hash proves file identity, not model accuracy.

4. Create a separate environment so the legacy environment remains available for rollback:

   ```bash
   python3 -m venv /home/growtechwall/venv-growtech-refactored
   source /home/growtechwall/venv-growtech-refactored/bin/activate
   python -m pip install "pip==25.1.1"
   cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall"
   python -m pip install -r requirements-pi.txt
   python -m pip check
   python -m pip freeze
   ```

   `requirements-pi.txt` is a proposed direct-dependency baseline derived from the captured Pi, not a reproduced lock file. Confirm an approved ARM wheel source for Torch/torchvision and choose the intended OpenCV distribution before treating installation as reproducible. ONNX is not required by the refactored `.pt` path; any future ONNX backend is a separate deferred change requiring a real `.onnx` model and comparative validation.

5. With no controller or camera interaction, run the headless suite:

   ```bash
   cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/refactored"
   python -m unittest discover -s tests -v
   ```

6. Run the GUI with simulation providers and verify all four tabs:

   ```bash
   python app.py --simulate
   ```

7. Close simulation mode. Only after the physical preflight is approved, start hardware mode manually:

   ```bash
   cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/refactored"
   source /home/growtechwall/venv-growtech-refactored/bin/activate
   python app.py
   ```

Hardware mode preserves `/dev/arduino_gantry`, `/dev/arduino_hydroponic`, `/dev/ttyAMA1`, 9600 baud, camera index `0`, and the legacy model path. Before importing hardware-provider modules, `app.py` requires Linux/aarch64 and Raspberry Pi device-tree model evidence; a failed platform check exits with instructions to use `--simulate` and does not open a device. This guard prevents accidental laptop hardware mode, but it does not authenticate the particular deployment or replace the preflight checks above. Opening the Nano USB ports may reset controllers, and the Gantry firmware homes at startup. Do not use hardware mode as the first installation smoke test.

## Exact Arduino compile and upload order

No Arduino toolchain or verified build metadata was available during desk implementation. Do not install tooling or select a convenient board profile as a substitute for the deployed metadata.

After the pre-deployment gate is complete, use this fixed order and change only one controller at a time:

1. **Capture both controllers first.** Save the current Gantry and Hydroponics source/flashed-artifact hashes when available, board settings, library versions, and a tested rollback command. Disconnect or isolate actuator/load power as required by the approved procedure.
2. **Compile the Gantry rewrite first.** Compile `gantry_main_refactored/gantry_main_refactored.ino` with the captured legacy Gantry board FQBN, processor/bootloader, compiler, and `AccelStepper` version. Do not upload if compilation differs unexpectedly or rollback is unavailable.
3. **Upload only the Gantry Nano.** Confirm the port by device metadata, keep the Hydroponics Nano unchanged, upload, then perform the Gantry-only startup, homing, endstop, 24-position, timeout, and recovery checks below.
4. **Gate or roll back.** If any Gantry result differs from the approved legacy expectation, stop, restore `gantry_main/gantry_main.ino` with its matching modules using the captured toolchain, and close the discrepancy before continuing.
5. **Compile the Hydroponics rewrite second.** Compile `NFT_Hydroponics_refactored/NFT_Hydroponics_refactored.ino` with the captured legacy Hydroponics board FQBN, processor/bootloader, compiler, `Wire`, and `RTClib` versions.
6. **Upload only the Hydroponics Nano.** Confirm the port by metadata, keep chemical loads disconnected or routed to the approved substitute-fluid setup, upload, then perform status, sensor, relay, timing, and recovery checks below.
7. **Gate or roll back.** If any Hydroponics result differs, restore the timestamped legacy sketch with the captured toolchain before integrated testing.
8. **Do not upload robotic-arm action files in this sequence.** The `.rob` loading procedure and exact deployed mapping remain unverified. Arm validation uses the already-deployed controller image only after its identity and group mapping are recorded.

“Gantry first, Hydroponics second” is the upload order. It does not resolve the missing board/toolchain metadata, and it is not authorization to upload.

## Physical prototype validation record

For every step, record date/time, operator and observer, Git commit, Pi/SD identity, controller identity, firmware hash, wiring/power state, expected result, observed result, logs or photographs, pass/fail, and rollback taken. A later document may use **hardware-validated future work** only for results supported by this record.

### 1. Serial aliases and native UART

With actuator and chemical-load power isolated, inspect without transmitting commands:

```bash
readlink -f /dev/arduino_gantry
readlink -f /dev/arduino_hydroponic
test -e /dev/arduino_roboticarm && echo present || echo absent
ls -l /dev/ttyAMA1
```

The legacy deployment evidence expects Gantry to resolve to `/dev/ttyUSB1`, Hydroponics to `/dev/ttyUSB0`, `/dev/arduino_roboticarm` to be absent, and the arm to use native `/dev/ttyAMA1`. The USB aliases are physical-topology mappings, not board-serial-number identities. Confirm device metadata; do not identify a controller by tty number alone.

### 2. Pi GUI startup and connection lifecycle

1. Start `python app.py --simulate`; verify the Dashboard, Gantry & Arm, Hydroponic, and Vision tabs and close it cleanly.
2. Establish the approved physical safe state and start `python app.py` once.
3. Record camera/model/controller connection messages and confirm the GUI remains responsive.
4. Close the GUI and verify workers and opened transports terminate. Do not infer actuator safe state merely because the process closed.
5. Start it a second time to characterize Nano reset/re-home behavior and confirm there is no port-lock leak.

### 3. Camera and YOLO

1. With controller movement inhibited, confirm camera index `0` is the intended USB camera and produces the expected 640 by 640 request.
2. Capture approved reference scenes for `No detection`, `Immatured`, `Matured`, and each deployed disease label.
3. Verify confidence threshold `0.3`, selection of the single highest-confidence detection whose center lies from `w/6` through `5w/6`, displayed label, annotation, and saved path `~/plant_images/<plant>/<YYYYmmdd_HHMMSS>.png`.
4. Compare results with the legacy application on the same saved frames. Record discrepancies; a matching model hash alone is insufficient.

### 4. Gantry startup, homing, and all 24 positions

1. Clear the motion envelope and establish the approved power-removal method.
2. Observe startup homing without issuing a movement command. Record endstop order, direction, dual-Y behavior, debounce/bump behavior, serial transcript, zero position, and completion.
3. Validate `0 0` re-home and explicitly record that the deployed legacy protocol completes with `Homing complete.` and does not emit `POS` for this command. Confirm the refactor advances on that line rather than waiting indefinitely. If a controller variant emits the legacy-expected fresh `POS 1 1`, record and validate that alternate accepted path separately.
4. Visit positions in the preserved snake order: `1,2,3,4,5,6,12,11,10,9,8,7,13,14,15,16,17,18,24,23,22,21,20,19`.
5. At each position, compare `START x y`, `POS x y`, physical alignment, direction, dual-Y squareness, and measured stop position with the legacy baseline.
6. Separately validate `U`, `D`, `L`, `R`, `G`, `P`, `X` during patrol, `O`, disabled-command re-enable/re-home behavior, and the 60-second inactivity home-and-disable behavior. Treat `O` as legacy home-Y-then-disable behavior, not an emergency stop.

### 5. Robotic-arm groups

Do not proceed until the deployed group mapping, fixtures, clearance envelope, and stop/power-removal procedure are physically confirmed. Validate one group at a time, with no Gantry movement and with a return-to-idle check between groups:

| Group | Legacy GUI meaning | Fixed wait used by Pi |
|---:|---|---:|
| 1 | Harvest pick-up | 4 s |
| 2 | Rotate/store in basket | 4 s |
| 3 | Pick seedling from rack | 5 s |
| 4 | Plant seedling | 7 s |
| 5 | Return to idle/camera mode | 1 s |
| 6 | Pesticide spray action | 10 s |

Confirm the exact binary frame `55 55 05 06 <group> 01 00`, actual completion time, final pose, and recovery for each deployed group. The legacy prototype groups reportedly worked, but the refactored arm transport requires this new physical validation.

### 6. Hydroponics status and sensors

1. Keep all pump/relay loads isolated. Capture startup output, RTC-present behavior, lost-power behavior, initial output levels, and the two 200 ms light-relay blinks.
2. Verify one complete `STAT,<ms>,<water>,<ec>,<ph>,<light>,<water>,<acid>,<fert>,<pest>` line per approximately 1000 ms and verify fragmented/combined input is displayed correctly by the Pi.
3. Compare raw readings and converted water, EC, and pH values with the legacy firmware under the same calibrated references. Do not approve accuracy without known solutions, calibration history, and sensor-condition records.

### 7. Individual water, light, and dosing outputs

Using electrically isolated indicators or the approved substitute-fluid setup, test only one output at a time:

1. `WATER_PUMP:ON`, then `WATER_PUMP:OFF`; confirm installed relay polarity and status.
2. `LIGHT:ON`, then `LIGHT:OFF`; confirm manual override and restoration through a valid light-hour command.
3. `DOSE:ACID:<mL>`; measure output duration and delivered substitute-fluid volume.
4. `DOSE:FERT:<mL>`; verify Fertilizer A and B activate and stop together, then measure both flows separately.
5. `DOSE:PEST:<mL>`; verify the preserved legacy limitation that the supplied mL does not set pesticide duration and that the current global `doseTimeMs` is used.
6. Validate `TARGET_EC`, `TARGET_PH`, `DOSE_TIME`, `LIGHT_ON_HOUR`, and `LIGHT_OFF_HOUR` with controlled values and no production chemicals.
7. Validate the ten-minute per-channel automatic EC and pH dose spacing with recorded simulated/reference sensor conditions. Do not shorten timing constants in a build claimed to be behavior preserving.

### 8. Automation dry run

1. Run Scan Only first with arm and chemical outputs isolated. Verify all 24 Gantry moves, captures, labels, image saves, cancellation boundaries, and completion state.
2. Resolve and document the home-completion behavior before Full Auto. The legacy `0 0`/`POS` mismatch is an explicitly documented bug; the refactored state transition must be compared against the accepted validation expectation.
3. Run Full Auto using inert props and substitute fluids only. For each label class, verify the preserved dispatch: no detection/immature to group 5; mature to harvest groups 1 and 2 followed by transplant groups 3 and 4 and group 5; other/disease to `DOSE:PEST:11`, group 6, then group 5.
4. Record Gantry/arm coordination at column 1, where harvest temporarily moves to column 2 for storage before returning.

### 9. Stop, failure, and recovery

Test cancellation at safe boundaries during scan, the 100-ms slices of the scan-only post-capture interval, Gantry wait, arm wait, capture, and hydroponics interaction. Confirm the GUI remains responsive and reports failure without Tk access from a worker. Then characterize controller disconnect/reconnect and application restart with loads isolated.

With actuator and dosing outputs isolated, validate each Phase 2C endpoint policy: startup failures leave the endpoint visibly offline; Gantry/Hydroponics/camera/model failures stop the affected operation and show an actionable error; an unavailable arm shows the legacy-compatible skip warning and the containing workflow continues; a failed pesticide dose stops before arm group 6; and no path silently retries or selects an alternate endpoint. Decide explicitly whether the arm skip-and-continue policy is acceptable before approving real workflows.

The acceptance record must state that GUI Stop cannot interrupt a blocking Nano move or an already-running arm group unless a separately approved, hardware-validated safety change has been implemented. Do not describe closing the GUI, `O`, serial disconnect, or a software timeout as an emergency stop.

## Rollback procedure

1. Stop the refactored application and remove actuator/load power using the approved physical procedure. Verify ports/processes are closed; independently establish hardware safe state.
2. If only Pi software changed, reactivate the untouched legacy environment and manual entry point:

   ```bash
   cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
   source /home/growtechwall/venv-ultralytics/bin/activate
   python3 GTW_GUIv2.py
   ```

   Start it only after the same physical preflight because legacy import opens the camera, native arm UART, and Nano ports.

3. If Gantry firmware changed, restore `gantry_main/gantry_main.ino` plus its matching `GantryController.h/.cpp` first, using the captured legacy FQBN/toolchain/library versions. Re-run the Gantry-only baseline checks before proceeding.
4. If Hydroponics firmware changed, restore `NFT_Hydroponics/NFT_Hydroponics_main_copy_20250609193150/NFT_Hydroponics_main_copy_20250609193150.ino` second, using its captured legacy build metadata. Re-run output-isolated status checks.
5. Do not alter or reload arm action files as a rollback shortcut until their controller-specific deployment mapping is verified.
6. If repository or environment recovery is required, restore the approved commit and, when necessary, the private SD-card image. Keep disk images and credentials outside Git.
7. Record the reason for rollback, exact artifacts restored, observed result, and any remaining unsafe or unknown state.

Rollback restores the known legacy software artifacts; it does not by itself prove wiring, calibration, arm pose, fluid state, or mechanical safety.
