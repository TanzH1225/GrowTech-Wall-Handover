# Raspberry Pi environment baseline

## Evidence and scope

The authoritative captured package/OS record is pi_runtime_environment_baseline_2026-07-17.txt. It was captured from the operational Pi environment and renamed in Phase 1 to remove a duplicate `.txt` extension without changing its contents.

This document summarizes captured facts and verified deployment evidence supplied for handover. It does not prove that a device is currently connected or that a hardware path is correct on a replacement Pi. Where a service/configuration is specifically labelled verified below, that statement is limited to the identified legacy Pi evidence.

## Verified captured baseline

| Item | Captured value |
|---|---|
| OS | Debian GNU/Linux 12 Bookworm |
| Architecture | `aarch64` |
| Python | 3.11.2 |
| Virtual environment | `/home/growtechwall/venv-ultralytics` |
| Virtual-environment isolation | `include-system-site-packages = false` |
| pip | 25.1.1 |
| Package health | `No broken requirements found.` |
| Repository location used by startup | `/home/growtechwall/Desktop/IDP-Grow-Tech-Wall` |

## Verified storage and boot layout

| Device | Verified role |
|---|---|
| `/dev/mmcblk0` | 116.5 GB SD card containing the current deployment |
| `/dev/mmcblk0p1` | Boot partition mounted at `/boot/firmware` |
| `/dev/mmcblk0p2` | Active root filesystem mounted at `/` |

The current deployment boots from an SD card. A private full-disk image of `/dev/mmcblk0` is recommended as a disaster-recovery artifact only. A disk image may contain credentials, network configuration, logs, user data, device rules, and other machine-specific information. Store it outside Git in access-controlled storage; do not commit it to this repository.

## Verified console auto-login and operator startup

The verified systemd drop-in is:

```text
/etc/systemd/system/getty@tty1.service.d/autologin.conf
```

Its verified content is:

```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin growtechwall --noclear %I $TERM
```

This override auto-logs the `growtechwall` account into the `tty1` console. It does not itself start the Tkinter application and must not be documented as GUI autostart.

The confirmed legacy operating procedure is manual GUI startup after boot:

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

No automatic GrowTech GUI launcher was discovered in the verified deployment evidence. The established procedure remains manual startup.

## Verified remote access

Remote access is configured and enabled through both SSH and Raspberry Pi Connect on the legacy Pi. This is verified deployment evidence, but the exact systemd unit names, service configuration files, SSH host keys, Raspberry Pi Connect account/authentication state, and access-control settings were not supplied to Phase 1C.

Sanitized service enablement and recovery requirements are safe to document. Credentials, private keys, host keys, account tokens, session data, and copied authentication state must not be committed. A replacement Pi should generate or enroll replacement credentials through the approved security process rather than cloning secrets from documentation.

## Runtime dependencies evidenced by source and capture

| Dependency | Captured version/evidence | Current purpose | Qualification |
|---|---|---|---|
| Ultralytics | 8.3.147 | Loads `bestv5.pt` and performs YOLO inference | Directly imported when available |
| Torch / torchvision | 2.7.0 / 0.22.0 | Ultralytics model runtime | ARM wheel source was not captured |
| OpenCV | `opencv-python` and `opencv-python-headless` 4.11.0.86 | Camera index `0`, image conversion/drawing/writing | Required variant has not been isolated |
| NumPy | 2.2.6 | Image tensor preparation and ONNX path | Direct import |
| Pillow | 11.2.1 | Tk image display | Direct import |
| pyserial | 3.5 | Gantry, hydroponics, and arm communication | Direct import |
| ONNX / ONNX Runtime | 1.17.0 / 1.22.0 | Intended fallback/export support | Current fallback incorrectly uses a `.pt` path |
| Tkinter / Tk | OS `python3-tk` / Tk 8.6 packages captured | 800×480 GUI | Requires a working desktop/display session |
| libcamera / Picamera2 | OS packages captured | Available Pi camera stack | Not imported by current GUI, which uses OpenCV USB camera access |
| GPIO and I2C packages | Multiple OS packages captured | General Pi capabilities | Not imported by the active GUI; hydroponics RTC I2C is on the Nano |

The package list contains many development and desktop packages that are not proven runtime requirements. A future minimal `requirements-pi.txt` must be validated on a replacement Pi rather than copying the complete freeze blindly.

## Camera, display, and native-UART boot configuration

The deployed system necessarily has camera/display/UART-related configuration, and active source opens native UART `/dev/ttyAMA1`. The exact legacy settings in `/boot/firmware/config.txt` and any related boot/session files were not supplied and remain unverified. Do not infer overlays or settings from the device path alone, and do not create a guessed replacement configuration.

Before replacement-Pi recovery, capture the exact legacy boot files, review them for device-specific or sensitive content, and validate camera, display/touchscreen, and UART separately.

## Current source-configured device paths

| Function | Source path | Baud | Source location |
|---|---|---:|---|
| Gantry Nano | `/dev/arduino_gantry` → `/dev/ttyUSB1` | 9600 | `GTW_GUIv2.py`; deployed alias resolution verified |
| Hydroponics Nano | `/dev/arduino_hydroponic` → `/dev/ttyUSB0` | 9600 | `GTW_GUIv2.py`; deployed alias resolution verified |
| Robotic-arm controller | Native UART `/dev/ttyAMA1` | 9600 | `ServoControl.py` |
| USB camera | OpenCV index `0` | — | `GTW_GUIv2.py` |

## Verified udev configuration supplied for handover

```udev
SUBSYSTEM=="tty", KERNELS=="3-2:1.0", SYMLINK+="arduino_gantry"
SUBSYSTEM=="tty", KERNELS=="1-1:1.0", SYMLINK+="arduino_hydroponic"
SUBSYSTEM=="tty", KERNELS=="1-2:1.0", SYMLINK+="arduino_roboticarm"
```

These rules match the physical USB topology represented by kernel paths such as `3-2:1.0`. They do **not** match board serial numbers. Moving a controller to another USB port, adding a hub, replacing a hub, or changing enumeration topology can cause a rule not to match or a symlink to identify a different device. The topology and device identity must be checked after any cable/port change.

Current verified resolution is:

```text
/dev/arduino_gantry      -> /dev/ttyUSB1
/dev/arduino_hydroponic  -> /dev/ttyUSB0
```

The `/dev/arduino_roboticarm` alias is currently absent.

The location/name of the deployed udev rules file was not captured in the repository. The exact rules above are preserved; their live installation and current matches were not rechecked during this software-only phase.

## Robotic-arm path discrepancy

The supplied udev configuration contains a rule that would request `/dev/arduino_roboticarm` for a USB tty at topology `1-2:1.0`, but that alias is currently absent. The active `Raspberry Pi/GUI/ServoControl.py` instead opens native UART `/dev/ttyAMA1`.

The inactive rule and active source path are preserved unchanged. Legacy prototype GUI arm action groups previously worked through the deployed arrangement, but the exact wiring, boot overlay, controller firmware, and action-file mapping remain unverified. Do not replace one path with the other. Any refactored arm-control code requires new controlled physical validation.

## Model and runtime paths

The active source selects:

```text
/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/bestv5.pt
```

Its repository SHA-256 at audit time was:

```text
87C36A815EE6A0EFDDE2BCB71BEC5B6CB1B8855A4958646DF56F4AFDC8EF9F19
```

The GUI writes captured images to `~/plant_images/<plant-number>/`. These are runtime data and are ignored by Git after Phase 1.

## Security and reproducibility

The environment capture contains no detected password, API token, private package URL, or credential. It does contain the username `growtechwall`, hostname `raspberrypi`, absolute home paths, detailed versions, and a machine fingerprint. The console auto-login drop-in also identifies a local account and grants console access without a password prompt. Treat these records as acceptable for controlled project handover but review physical-access risk and sanitize machine-identifying details before intentional public publication.

Still unverified or uncaptured:

- udev rules file name and the output of `udevadm info` for each live controller;
- memberships/permissions for serial and camera devices;
- UART overlays and `/boot/firmware/config.txt` settings for `/dev/ttyAMA1`;
- camera make, USB identity, stable index, supported formats, and permissions;
- desktop/display manager and touchscreen configuration;
- exact SSH and Raspberry Pi Connect unit/configuration/authentication details;
- any GUI application-autostart configuration; no automatic GrowTech launcher was discovered and the verified operator procedure is manual startup;
- Torch/torchvision ARM wheel source;
- firmware toolchain, board selection, library versions, and flashed hashes.

See [pi-deployment-manifest.md](pi-deployment-manifest.html) for the consolidated artifact/configuration inventory and [new-pi-recovery.md](new-pi-recovery.html) for the recovery sequence and validation gates.
