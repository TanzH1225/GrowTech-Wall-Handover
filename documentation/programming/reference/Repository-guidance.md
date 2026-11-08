# GrowTech Wall repository guidance

This repository contains a physically operational legacy automation system. Treat the checked-in executable code, controller protocols, pin maps, timings, model behavior, and firmware as preservation-sensitive until a change has been separately tested on the real system.

## Repository layout and controller architecture

- `Raspberry Pi/GUI/GTW_GUIv2.py`: current Raspberry Pi touchscreen GUI, USB-camera/YOLO vision, and system coordinator.
- `Raspberry Pi/GUI/ServoControl.py`: direct binary protocol client for the robotic-arm action controller.
- `gantry_main/`: current gantry Arduino Nano firmware. It owns stepper drivers, dual-Y and X motion, homing, endstops, grid coordinates, and motor enable/disable behavior.
- `NFT_Hydroponics/NFT_Hydroponics_main_copy_20250609193150/`: authoritative current hydroponics Arduino Nano firmware. It owns sensing, calibration calculations, RTC lighting, water, fertilizer A+B, acid, and pesticide outputs.
- `NFT_Hydroponics/NFT_Hydroponics.ino`: older historical hydroponics firmware retained for traceability. Do not substitute it for the timestamped baseline.
- `Arm Action File/`: binary action-group deployment files for the separate robotic-arm controller. Their exact board-loading procedure and mapping remain physically unverified in repository documentation.
- `docs/`: audited baseline, deployment manifest, protocols, environment recovery, limitations, and refactoring status.

The four active control roles are:

1. Raspberry Pi GUI/vision/coordinator.
2. Gantry Arduino Nano.
3. Hydroponics Arduino Nano.
4. Robotic-arm action controller, commanded directly by the Pi rather than by either Nano.

The Pi supervises the system. It does not directly own gantry motor pins, hydroponics relays, or hydroponics sensor acquisition.

## Current Raspberry Pi startup baseline

The verified legacy operator procedure is manual GUI startup after the Pi has booted. The current Pi boots from an SD card, and `tty1` is configured to auto-login the `growtechwall` user. Console auto-login does not establish or imply GUI application autostart.

```sh
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

Running this command can initialize a camera and serial devices and can cause connected controllers to reset or home. Do not run it during laptop or software-only work.

## Verified Pi deployment baseline

- Boot device: `/dev/mmcblk0`, a 116.5 GB SD card.
- Firmware boot partition: `/dev/mmcblk0p1`, mounted at `/boot/firmware`.
- Root filesystem: `/dev/mmcblk0p2`, mounted at `/`.
- Console auto-login override: `/etc/systemd/system/getty@tty1.service.d/autologin.conf`.
- Console auto-login user: `growtechwall`.
- GUI operation after boot: manual execution of the startup commands above.
- No automatic GrowTech GUI launcher was discovered in the verified deployment evidence.
- Remote access is configured through enabled SSH and Raspberry Pi Connect.
- Gantry alias: `/dev/arduino_gantry` → `/dev/ttyUSB1`.
- Hydroponics alias: `/dev/arduino_hydroponic` → `/dev/ttyUSB0`.
- Robotic arm: native UART `/dev/ttyAMA1`; `/dev/arduino_roboticarm` is currently absent and inactive.

A private full-disk image of the SD card may be maintained for disaster recovery. Disk images can contain credentials, device configuration, logs, and user data; keep them outside Git in controlled storage. Do not add a Pi disk image to this repository.

## Preservation requirements

- Keep `GTW_GUIv2.py` as the startup entry point until an approved phase explicitly changes that contract.
- Do not change existing serial ports, baud rates, command text, delimiters, responses, arm binary frames, or controller reset behavior without captured protocol fixtures and physical validation.
- Preserve gantry pin assignments, active levels, motor direction inversion, measured grid-step arrays, speeds, acceleration, homing behavior, debounce, delays, and timeout behavior during behavior-preserving refactors.
- Preserve hydroponics pin assignments, relay polarity, RTC behavior, sensor conversions, dose-duration assumptions, timing intervals, status layout, and command parsing during behavior-preserving refactors.
- Preserve the active `bestv5.pt` model, confidence threshold, ROI, label interpretation, camera resolution, and saved-image behavior unless an approved vision change includes comparative evidence.
- Never delete or silently merge historical firmware, calibration sketches, model variants, or arm action files merely because they appear duplicated or obsolete.
- Preserve documented Pi boot, udev, console auto-login, UART, service, and operator-startup configuration as evidence. Do not modify live Pi configuration during a behavior-preserving software phase.
- Treat missing wiring, calibration provenance, pump flow, arm-action mapping, controller build settings, and physical stop behavior as unverified. Documentation must not promote an inference into a verified fact.

## Laptop and desk testing

- Use mocks, prerecorded serial transcripts, fake transports, prerecorded images, and simulated controller state for laptop tests.
- Do not import `GTW_GUIv2.py` or `ServoControl.py` as a test shortcut: both contain top-level hardware initialization.
- Pure protocol parsing, state transitions, configuration, image-file inference, and GUI logic behind injected mocks may be tested on Windows.
- Tests must not open `/dev/arduino_*`, `/dev/ttyAMA1`, `COM*`, camera index `0`, GPIO, I2C, or relay/motor interfaces.
- A desk test or successful firmware compilation is not physical validation.

## Validation terminology

- **Verified legacy behavior**: directly evidenced by the checked-in source, captured environment, Git history, or an explicitly recorded observation of the legacy system.
- **Desk-verified future work**: new behavior checked with static analysis, mocks, fixtures, or laptop tests only.
- **Hardware-validated future work**: new behavior tested on the identified Pi/controller/hardware configuration with results recorded in documentation.
- **Deferred improvement**: proposed but not implemented or validated.

Never claim hardware validation without an actual physical test record containing the hardware state, procedure, expected result, observed result, date, and operator.

## Expected workflow

1. Confirm the repository, branch, and clean/known worktree state.
2. Read `docs/legacy-system-audit.md`, `docs/known-limitations.md`, and `docs/refactoring-status.md`.
3. Use `docs/pi-deployment-manifest.md` when changing or recovering Pi deployment configuration.
4. Capture characterization fixtures before changing a behavior boundary.
5. Implement one small, reversible phase while preserving unrelated user changes.
6. Run text/static checks and mock-based laptop tests.
7. Review the diff specifically for changes to protocols, pins, timing, paths, model behavior, and top-level hardware initialization.
8. Perform physical testing only when explicitly authorized and document the result.
9. Do not merge into `main` until the phase's required physical checks pass.

## Safe verification commands

These commands inspect repository state and text only:

```sh
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git diff --check
git diff --stat
git diff -- "Raspberry Pi/GUI/GTW_GUIv2.py" "Raspberry Pi/GUI/ServoControl.py" gantry_main NFT_Hydroponics
rg -n "(/dev/arduino_|/dev/ttyAMA1|9600|MODEL_PATH)" "Raspberry Pi/GUI" gantry_main NFT_Hydroponics docs
```

Once a mock-only test suite exists, its expected laptop command is:

```sh
python -m pytest tests -q
```

Do not run that command until the test configuration guarantees that hardware transports and camera providers are replaced by mocks. Firmware compilation is a separate desk check; board type, library versions, and compiler settings must be captured before a compile result can be compared with the legacy firmware.
