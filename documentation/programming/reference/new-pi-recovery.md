# New Raspberry Pi recovery and deployment guide

## Purpose and safety boundary

This guide defines a reproducible recovery target from captured software evidence. It has not been executed on a replacement Pi during Phase 1. Steps that open the GUI or serial ports can reset/home connected controllers and initialize the camera; perform them only during an explicitly authorized physical validation with the system made safe.

Use [pi-deployment-manifest.md](pi-deployment-manifest.html) as the inventory of source locations, commit policy, verification status, and replacement-Pi actions.

Do not connect actuator power merely to validate package installation. Do not upload firmware as part of Pi recovery unless the controller baseline, board type, toolchain, and rollback image have been separately verified.

## 1. Preserve the old Pi before replacement

With appropriate authorization, capture or back up:

- repository commit and worktree status;
- block-device and mount output confirming the active root and boot partitions;
- `/home/growtechwall/venv-ultralytics` package freeze and package health;
- udev rules and `udevadm info` for every controller;
- `/boot/firmware/config.txt`, UART overlays, groups, and device permissions;
- `/etc/systemd/system/getty@tty1.service.d/autologin.conf`;
- SSH and Raspberry Pi Connect service/configuration state without copying credentials or tokens;
- desktop/display and any application-autostart service definitions;
- USB camera identity and supported modes;
- model files and SHA-256 hashes;
- serial startup transcripts with actuator power isolated;
- firmware/toolchain metadata and any known-good firmware artifacts.

Several of these items were not included in the 2026-07-17 capture and remain required for confident recovery.

The current deployment uses a 116.5 GB SD card at `/dev/mmcblk0`. For disaster recovery, maintain a private full-disk image of that device using an approved imaging process. Store the image outside Git in access-controlled, preferably encrypted storage and document its creation date and source Pi. A disk image is a machine-recovery artifact, not a replacement for source control or a reproducible installation guide, and must not be committed to this repository.

## 2. Establish the OS baseline

Use a Raspberry Pi OS environment compatible with the captured Debian 12 Bookworm `aarch64` baseline and Python 3.11.2. Record the image release and package sources. Do not silently substitute a newer Python, OS, camera stack, or architecture in a baseline recovery.

The verified legacy storage layout is:

| Device | Legacy role |
|---|---|
| `/dev/mmcblk0` | 116.5 GB SD card |
| `/dev/mmcblk0p1` | Mounted at `/boot/firmware` |
| `/dev/mmcblk0p2` | Active root filesystem mounted at `/` |

A restored disk image may be written to replacement media of suitable capacity as part of controlled disaster recovery. After restoration, verify the actual block devices and mounts rather than assuming Linux device names or partition expansion behavior.

Verify the availability of the captured OS-level capabilities:

- `python3-venv` and `python3-tk`;
- a working desktop/display session for Tkinter;
- libcamera/camera tooling appropriate to the connected camera;
- serial/udev support;
- permissions for camera and tty devices.

The active GUI does not directly require Pi GPIO or Pi I2C. GPIO/I2C packages present in the old image should not be interpreted as evidence that the Pi owns hydroponics pins or sensors.

Exact legacy camera, display/touchscreen, and native-UART settings in `/boot/firmware/config.txt` or related files were not supplied to Phase 1C. Capture and review the real files before rebuilding; do not infer overlays or create guessed boot configuration from `/dev/ttyAMA1` alone.

## 3. Restore the repository and model

Clone or copy the repository to the path expected by the current entry point:

```text
/home/growtechwall/Desktop/IDP-Grow-Tech-Wall
```

Check out the approved commit/branch. Confirm the active model exists at:

```text
/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/bestv5.pt
```

Verify its expected audit-time SHA-256:

```text
87C36A815EE6A0EFDDE2BCB71BEC5B6CB1B8855A4958646DF56F4AFDC8EF9F19
```

A matching hash proves file identity only; it does not prove labels, camera alignment, accuracy, or physical validation.

## 4. Recreate the Python environment

The captured environment used:

```sh
python3 -m venv /home/growtechwall/venv-ultralytics
source /home/growtechwall/venv-ultralytics/bin/activate
```

A future reviewed `requirements-pi.txt` should start from the direct runtime set below, while retaining a separate full freeze for forensics:

```text
numpy==2.2.6
pillow==11.2.1
pyserial==3.5
opencv-python==4.11.0.86
torch==2.7.0
torchvision==0.22.0
ultralytics==8.3.147
onnxruntime==1.22.0  # only if a valid ONNX fallback remains supported
```

No requirements file was created in Phase 1. Before adopting this list:

- determine the verified ARM wheel source for Torch/torchvision;
- choose one appropriate OpenCV distribution instead of assuming both captured distributions are required;
- decide whether ONNX Runtime is a supported backend and point it to a real `.onnx` model;
- run `python -m pip check` and record the complete resolved freeze.

## 5. Restore stable serial aliases

The verified udev configuration supplied for handover is:

```udev
SUBSYSTEM=="tty", KERNELS=="3-2:1.0", SYMLINK+="arduino_gantry"
SUBSYSTEM=="tty", KERNELS=="1-1:1.0", SYMLINK+="arduino_hydroponic"
SUBSYSTEM=="tty", KERNELS=="1-2:1.0", SYMLINK+="arduino_roboticarm"
```

These are physical USB-topology mappings, not board-serial-number mappings. Install them in an appropriately named root-owned file under `/etc/udev/rules.d/` only after confirming that the replacement Pi has the same intended port/hub topology. Record the chosen file name. After reloading rules or reconnecting devices, verify that each symlink resolves to the intended controller using device metadata and controller-safe identification procedures.

The verified legacy deployment currently resolves:

```text
/dev/arduino_gantry      -> /dev/ttyUSB1
/dev/arduino_hydroponic  -> /dev/ttyUSB0
```

`/dev/arduino_roboticarm` is currently absent and must not be treated as active. The arm uses native UART `/dev/ttyAMA1` in current source.

Do not identify a controller merely because a symlink exists. Do not send an actuator command as the first identity test.

## 6. Restore console login behavior and retain manual GUI startup

The verified legacy console auto-login drop-in is:

```text
/etc/systemd/system/getty@tty1.service.d/autologin.conf
```

with exact content:

```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin growtechwall --noclear %I $TERM
```

This configuration auto-logs `growtechwall` into the `tty1` console. It is security-sensitive because physical console access obtains a logged-in user session. Restore it only when reproducing the approved legacy operator environment, with appropriate ownership and physical-access review.

Console auto-login does not start the GUI. The confirmed legacy operator procedure is manual startup after boot:

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

No automatic GrowTech GUI launcher was discovered in the verified deployment evidence. Do not invent an application autostart unit or desktop entry during baseline recovery. Any future GUI autostart is a separate deployment change requiring review and safe startup validation.

## 7. Re-establish remote access deliberately

The legacy deployment has both SSH and Raspberry Pi Connect enabled/configured. Exact unit names, configuration files, SSH host keys, Raspberry Pi Connect account state, and authentication tokens were not captured in the Phase 1 documentation.

On a replacement Pi:

1. Configure SSH using newly generated host keys and approved user authentication; do not copy private keys or passwords into Git.
2. Install/enable Raspberry Pi Connect using the approved account enrollment process; do not copy tokens/session state into Git.
3. Apply network and access restrictions appropriate to the deployment.
4. Record service state and non-secret configuration for handover.
5. Treat remote-access success as deployment validation only; it does not validate the GUI or hardware controllers.

## 8. Resolve—do not guess—the arm interface

The udev rules create `/dev/arduino_roboticarm`, but `ServoControl.py` opens `/dev/ttyAMA1`. Preserve both until the old installation is inspected. Capture:

- what cable/interface physically connects the arm controller;
- whether `/dev/ttyAMA1` is enabled and which overlay configures it;
- why the retained `/dev/arduino_roboticarm` rule exists even though the alias is currently absent;
- whether the arm can be safely identified without motion;
- controller model, firmware, and action-group deployment process.

Changing `ServoControl.py` or the udev rule is a future behavior change, not a Phase 1 recovery shortcut.

Legacy prototype GUI action groups previously worked through the deployed native-UART arrangement. Any refactored arm-control code, replacement transport, or restored action mapping still requires a new controlled physical validation record.

## 9. Validate software without live hardware

Before attaching controllers or a camera:

1. Verify repository and model hashes.
2. Import third-party dependencies in an isolated diagnostic that does not import `GTW_GUIv2.py` or `ServoControl.py`.
3. Run protocol parser and state-machine tests using fixtures/mocks when those tests exist.
4. Test image-file inference using approved prerecorded images, not camera index `0`.
5. Test GUI code only after hardware providers can be injected as mocks.

Passing these checks is **desk verification**, not hardware validation.

## 10. Controlled physical validation gate

Only after explicit authorization and a reviewed safety checklist:

1. Confirm device identities and permissions with actuator power isolated.
2. Verify the camera identity and one non-actuating capture path.
3. Capture controller startup output and reset behavior.
4. Validate each protocol with a defined safe test, rollback, and observer.
5. Test gantry, arm, sensors, and relays separately before any integrated workflow.
6. Record date, operator, hardware configuration, expected result, observed result, and pass/fail.

The current startup command is:

```sh
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

Do not use it as an initial software smoke test: importing the application opens camera and serial interfaces, and connected Nanos may reset or home.

## 11. Recovery gaps

Storage layout, SD-card boot, the `tty1` console auto-login drop-in, manual GUI startup, enabled SSH/Raspberry Pi Connect, gantry/hydro alias resolutions, native-UART arm path, and the absence of `/dev/arduino_roboticarm` are now documented from verified deployment evidence. Recovery still cannot be claimed reproducible for exact remote-access service/authentication configuration, desktop/display/touchscreen configuration, camera/UART boot settings, any GUI application-autostart configuration, USB camera identity, arm wiring/action mapping, udev installation path, serial permissions, Torch wheel source, firmware flashes, calibration, wiring, or pump flow. Each is an explicit evidence-gathering item, not a fact to infer.
