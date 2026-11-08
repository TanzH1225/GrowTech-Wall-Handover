# GrowTech Wall legacy-system audit

> Current-source note (2026-10-09): This is a historical July audit. The [2026-10-09 programming handover](../README.html) inspects current refactored and legacy source; its [evidence record](../08-evidence-and-change-record.html) identifies later arm-refresh, reset, gantry, dependency and Git-status differences. Historical findings below are not automatically descriptions of current HEAD.

## Audit status

- Audit date: 2026-07-17.
- Source branch at audit time: `refactor/gui-architecture`.
- Method: repository source, Git history, file metadata, captured Raspberry Pi environment, and subsequently supplied verified Pi deployment evidence.
- No GUI, camera, GPIO, serial device, Arduino, relay, pump, motor, or robotic arm was activated during the audit.
- The findings labelled **source-verified** are verified from repository evidence, not from a new physical test.
- Wiring, calibration provenance, pump flow, arm action deployment, and actual fault response remain unverified unless explicitly stated otherwise.

## Executive summary

GrowTech Wall is a distributed four-controller system:

1. The Raspberry Pi provides the Tkinter GUI, USB-camera capture, YOLO inference, serial supervision, and cross-controller workflow coordination.
2. The gantry Arduino Nano owns three stepper channels, homing, endstops, measured grid positions, and motor-driver enable behavior.
3. The hydroponics Arduino Nano owns its RTC, sensor acquisition, calibrated values, lighting, water pump, fertilizer A+B, phosphoric-acid pump, and pesticide pump.
4. A separate robotic-arm action controller receives binary action-group commands directly from the Pi over UART.

The Pi does not directly manipulate gantry or hydroponics GPIO. It does directly command the robotic-arm controller through `ServoControl.py`.

Overall maintainability is low. `Raspberry Pi/GUI/GTW_GUIv2.py` is a 1,723-line top-level program containing imports, hardware initialization, GUI construction, serial transport, protocol parsing, computer vision, automation, and error handling. Staged refactoring is nevertheless feasible because the controller boundaries and most current wire formats can be identified from source.

The recommended principle is: characterize and preserve physical behavior first, then extract one boundary at a time behind the existing protocol and validate each phase before merging to `main`.

## Highest-priority risks

1. **Automation homing handshake mismatch.** `automation_full_loop()` waits for a reached UI state after sending `0 0`, but the gantry re-home path does not emit `POS`. This can wait indefinitely. The scan-only loop can pass its home wait using already-mutated GUI state instead of a new hardware confirmation.
2. **No interruptible system stop.** The GUI stop event stops Pi orchestration between operations. It cannot interrupt a blocking gantry move or an arm action already sent. Gantry command `O` homes the dual-Y axes before disabling motors and is not an emergency stop.
3. **Hydroponics dosing safeguards are incomplete.** Source contains no water-presence interlock, sensor plausibility validation, stable-sample requirement, chemical mutual exclusion, or upper bound for target/dose commands.
4. **Serial transport is not transactional.** There are no sequence numbers, correlated acknowledgements, retries, write locks, or automatic reconnect. Hydroponics input is read as arbitrary chunks rather than buffered complete lines.
5. **Deployment cannot yet be reproduced confidently.** The repository lacks a Pi requirements file, udev/configuration capture, firmware toolchain metadata, model manifest, wiring diagram, calibration history, arm action mapping, and physical validation records.

## Repository inventory

| Path | Classification | Runtime role | Notes |
|---|---|---|---|
| `Raspberry Pi/GUI/GTW_GUIv2.py` | Python source | Active Pi entry point | Hard-coded model/device paths; top-level initialization |
| `Raspberry Pi/GUI/ServoControl.py` | Python source/protocol | Active arm client | Opens `/dev/ttyAMA1` at import |
| `Raspberry Pi/GUI/arduino_gui.py` | Python source | Historical prototype | Not imported by active GUI |
| `Raspberry Pi/GUI/best*.pt`, `best*.onnx` | AI models | Only `bestv5.pt` is selected by active source | Nine files total, 76.55 MiB; model provenance is absent |
| `Arm Action File/*.rob` | Binary deployment assets | External arm controller | File-to-action-group deployment process is unverified |
| `gantry_main/` | Arduino firmware | Gantry Nano baseline | Uses `AccelStepper` |
| Timestamped NFT folder | Arduino firmware | Hydroponics Nano baseline | Uses `Wire` and `RTClib` |
| Root `NFT_Hydroponics.ino` | Arduino firmware | Historical only | Protocol-incompatible with current GUI |
| `ECcalibration.ino`, `pHcalibration.ino` | Calibration source | Bench utilities | Constants and pins differ from active firmware |
| `IDP/`, `Gantry System/`, `ClockModule/`, `LightStatus/` | Arduino source | Historical/test material | Not established as active firmware |
| `docs/pi_runtime_environment_baseline_2026-07-17.txt` | Environment capture | Recovery evidence | Contains machine-specific username, hostname, and paths |

The repository contains no checked-in virtual environment, Python cache, runtime log, or generated Arduino `.hex/.elf` image. The active model `bestv5.pt` has SHA-256 `87C36A815EE6A0EFDDE2BCB71BEC5B6CB1B8855A4958646DF56F4AFDC8EF9F19`; `bestv3.pt` is byte-identical. This does not establish that either model is physically validated or document its training data/classes.

## Raspberry Pi execution flow

At process import, the application:

1. Imports Tkinter, Pillow, pyserial, threading, OpenCV, NumPy, optional Ultralytics or ONNX Runtime, and local `ServoControl`.
2. Loads `/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/bestv5.pt` with Ultralytics when available. The log incorrectly describes it as an ONNX model. The fallback attempts to give the same `.pt` path to ONNX Runtime and is not a valid fallback.
3. Opens OpenCV camera index `0` and requests 640 by 640 pixels.
4. Imports `ServoControl`, which opens `/dev/ttyAMA1` at 9600 baud.
5. Opens `/dev/arduino_gantry` and `/dev/arduino_hydroponic` at 9600 baud, sleeps after each open, and resets their buffers.
6. Constructs a Tk root window and four tabs: Dashboard, Gantry & Arm, Hydroponic, and Vision.
7. Starts a daemon serial reader before entering `root.mainloop()`.

`capture_and_infer()` flushes camera frames, applies YOLO with confidence threshold `0.3`, accepts detections whose center is between `w/6` and `5w/6`, selects the highest-confidence detection, updates UI state, and writes an annotated image under `~/plant_images/<plant-number>/`.

Manual operation includes grid/relative gantry commands, arm action groups, hydroponics controls, and capture. Automated operation visits 24 plant positions in snake order. Full mode interprets `No detection`/`Immatured` as idle, `Matured` as harvest plus transplant, and other labels as pesticide handling.

The reader, automation, capture, and arm workflows use daemon threads. Several worker functions directly access Tk variables and widgets. Resetting serial connections runs sleeps on the GUI thread and has no synchronization with the reader. Shutdown releases the camera but does not close all serial ports, stop/join workers, stop the arm, or issue a controller safe-state transaction.

## Controller ownership summary

| Subsystem | Owner | Pi role |
|---|---|---|
| GUI and displayed state | Raspberry Pi | Owner |
| USB camera, YOLO, saved images | Raspberry Pi | Owner |
| X/Y gantry motion, stepper drivers | Gantry Nano | Command/status client |
| Homing and endstops | Gantry Nano | Command/status client |
| Robotic-arm actions | Separate arm controller | Direct binary command client and workflow coordinator |
| Water, EC, and pH acquisition | Hydroponics Nano | Display/status client |
| Sensor conversion/calibration math | Hydroponics Nano | Displays converted values |
| Water, fertilizer A/B, acid, pesticide, light | Hydroponics Nano | Sends settings/commands |
| Plant scan/harvest/transplant coordination | Raspberry Pi | Owner |
| Autonomous lighting and nutrient/acid dosing | Hydroponics Nano | Sets targets/schedule |

## Gantry firmware baseline

Source-verified pins are X step/dir D2/D3, Y1 D4/D5, Y2 D6/D7, endstops D8/D9/D10 with internal pull-ups, and driver enables A0/A1/A2 active low. X uses 40 steps/mm and Y uses 26.667 steps/mm. Configured movement speed is 300 mm/s, acceleration is 5,000 steps/s², fast homing is 75 mm/s, slow homing is 10 mm/s, bump distance is 10 mm, debounce is 50 ms, and each homing approach has a 15-second timeout. The controller holds measured X step positions for four rows by six columns and four measured Y positions.

Startup waits two seconds and homes all axes. After sixty seconds of inactivity the controller homes and disables the motors. Motion and homing loops are blocking. Normal moves use software bounds and do not check endstops continuously. `errorStop()` enters an infinite loop after calling `stop()` without running the deceleration or explicitly disabling drivers. These are legacy behaviors to document, not endorsements of safety.

## Hydroponics firmware baseline

The timestamped folder is the current baseline. Source-verified pins are acid D2, fertilizer B D3, fertilizer A D4, water D5, light D9, pesticide D10, water level A0, EC A1, and pH A2. Chemical relays are documented as normally open with high=on; water and light are documented as normally closed with low=on. Actual wiring polarity requires physical validation.

The firmware initializes pumps off, blinks the light twice, reads a DS3231 RTC, reports calibrated sensor values each second, and implements configurable lighting and dosing targets. Its default dose duration is five seconds under an assumed one millilitre per second flow rate. Automatic EC and pH doses are separated by at least ten minutes. These flow and chemical assumptions have not been physically verified by this audit.

The root historical firmware is different: it accepts single-letter commands and range settings, reports raw ADC values with timestamped `STATUS:` records, uses a fixed dose duration, and lacks the newer ten-minute auto-dose spacing. Commit `0bff38c` added the timestamped firmware while modifying the GUI, which supports an inference that it was introduced for the newer GUI protocol. The commit message does not prove physical validation.

## Environment baseline

The captured environment verifies Debian GNU/Linux 12 Bookworm on `aarch64`, Python 3.11.2, `/home/growtechwall/venv-ultralytics`, pip 25.1.1, and `pip check` reporting no broken requirements. Key pip versions include Ultralytics 8.3.147, Torch 2.7.0, torchvision 0.22.0, OpenCV 4.11.0.86, NumPy 2.2.6, Pillow 11.2.1, pyserial 3.5, ONNX 1.17.0, and ONNX Runtime 1.22.0.

The package capture also shows Tkinter, libcamera/Picamera2, GPIO, serial, and I2C-related OS packages. The active GUI uses Tkinter, pip pyserial, OpenCV USB camera access, and the arm UART. It does not import Picamera2, GPIO, or Pi I2C libraries. Installed package presence does not prove service state or configuration.

Subsequent verified deployment evidence establishes that the current Pi boots from a 116.5 GB SD card at `/dev/mmcblk0`, with `/dev/mmcblk0p1` mounted at `/boot/firmware` and root filesystem `/dev/mmcblk0p2` mounted at `/`. It also establishes a `tty1` console auto-login drop-in at `/etc/systemd/system/getty@tty1.service.d/autologin.conf` for user `growtechwall`.

Console auto-login must not be conflated with GUI autostart. The confirmed legacy operating procedure is manual execution after boot:

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

No automatic GrowTech GUI launcher was discovered in the verified deployment evidence. SSH and Raspberry Pi Connect are enabled/configured for remote access, although exact service units, credentials, tokens, host keys, and access restrictions were not captured in the repository.

The current Nano aliases resolve as `/dev/arduino_gantry` → `/dev/ttyUSB1` and `/dev/arduino_hydroponic` → `/dev/ttyUSB0`. Both are topology-based udev aliases rather than serial-number identities. The robotic arm uses native UART `/dev/ttyAMA1`; the retained `/dev/arduino_roboticarm` rule does not currently produce an active alias. Legacy prototype arm groups previously worked, but any refactored arm-control code requires new physical validation.

A private full-SD-card image is appropriate as a disaster-recovery artifact, but it may contain sensitive machine data and must remain outside Git.

No credentials, tokens, or private package URLs were found in the baseline. It does expose the local username, hostname, home path, and a detailed machine fingerprint. Sanitize those details before intentional public publication.

## Refactoring conclusion

A full rewrite is neither necessary nor appropriate. First capture protocol fixtures, controller configuration, firmware build metadata, model metadata, and physical test results. Then centralize configuration, isolate transports, isolate vision, separate automation from widgets, and only afterward consider internal firmware refactoring. Safety changes such as acknowledgements, interruptible stop behavior, input limits, sensor validation, and dosing interlocks are intentional behavior changes and require separate approval and physical fault testing.

See [controller-responsibility-map.md](controller-responsibility-map.html), [pi-nano-protocol.md](pi-nano-protocol.html), [known-limitations.md](known-limitations.html), and [refactoring-status.md](refactoring-status.html) for maintained handover records.
