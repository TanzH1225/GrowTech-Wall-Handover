# Raspberry Pi deployment manifest

## Purpose and evidence boundary

This manifest consolidates repository evidence, the captured 2026-07-17 Pi environment, and deployment facts explicitly verified by the project operator. Phase 1C did not read or modify the live Pi. Exact values not supplied—especially wiring, calibration, action mapping, firmware build settings, and boot-file contents—remain unverified.

“Safe to commit?” distinguishes sanitized handover documentation from machine images, credentials, tokens, mutable runtime state, and unreviewed system files.

## Deployment artifacts and configuration

| Artifact/configuration | Source location | Purpose | Verified status | Safe to commit? | Replacement-Pi action |
|---|---|---|---|---|---|
| SD-card device | Active Pi `/dev/mmcblk0` | Current boot and root storage | Verified as a 116.5 GB SD card | Device fact: yes | Use compatible media; verify actual device identity/capacity before imaging or restoring |
| Boot partition | `/dev/mmcblk0p1`, mounted at `/boot/firmware` | Firmware and Pi boot configuration | Verified current mount | Sanitized mount fact: yes | Recreate/restore from an approved image or OS installation; verify mount after boot |
| Root filesystem | `/dev/mmcblk0p2`, mounted at `/` | Active operating-system root | Verified current root filesystem | Sanitized mount fact: yes | Recreate/restore and verify with block/mount inspection; do not assume device naming blindly |
| Full SD-card image | Private recovery storage; source device `/dev/mmcblk0` | Disaster recovery for the complete deployed Pi | Recommended policy; no image is stored in Git | **No—never Git** | Create using an approved offline process; store access-controlled, preferably encrypted, with date/hash/source metadata |
| tty1 console auto-login | `/etc/systemd/system/getty@tty1.service.d/autologin.conf` | Auto-login `growtechwall` on console tty1 | Exact file path and content verified | Sanitized documented content: yes; credentials: never | Restore only if approved for the replacement environment; verify ownership/permissions and physical-access risk |
| Manual GrowTech GUI startup | Operator procedure in `/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI` | Start the active Tkinter/vision/coordinator application after boot | Confirmed legacy operating procedure | Yes | Activate the verified venv and run `python3 GTW_GUIv2.py` manually after safe device checks |
| Automatic GrowTech GUI launcher | systemd/desktop/session configuration on active Pi | Would launch the application without the manual command | No automatic GrowTech GUI launcher was discovered in the verified deployment evidence | Absence finding: yes | Do not invent an autostart unit during baseline recovery; treat future autostart as a separately validated change |
| SSH remote access | Active Pi service state; exact unit/config files not captured | Remote shell administration | Verified enabled/configured on the legacy Pi | Enablement fact: yes; host keys, credentials, and private config: no | Configure deliberately, generate replacement credentials/host keys, restrict access, and verify service state |
| Raspberry Pi Connect | Active Pi service/account state; exact unit names and authentication state not captured | Raspberry Pi remote access | Verified enabled/configured on the legacy Pi | Enablement fact: yes; account tokens/session data: no | Install/enable using the approved account and security process; never copy tokens into Git |
| Camera/display/UART boot configuration | Primarily `/boot/firmware/config.txt`; related boot/session files may also apply | Enable/configure camera, display/touchscreen, and native UART behavior | Configuration category is required, but exact legacy contents/settings were not supplied and remain unverified | Not until captured and reviewed; never commit guessed content or secrets | Capture exact legacy files/settings, review for machine-sensitive data, restore only required settings, and validate each device separately |
| Python virtual environment | `/home/growtechwall/venv-ultralytics` | Python 3.11 GUI, vision, and serial runtime | Path, Python 3.11.2, pip 25.1.1, freeze, and healthy `pip check` captured | Venv directory: no; sanitized requirements/freeze: yes after review | Recreate rather than copy; verify ARM package sources, dependency imports, and `pip check` |
| Active AI model | `Raspberry Pi/GUI/bestv5.pt` | Ultralytics YOLO inference | Source selection and repository SHA-256 recorded; model accuracy/provenance not established | Already tracked; yes under current repository policy | Restore exact file/hash first; validate labels, camera geometry, and inference physically before claiming equivalent operation |
| Other `.pt`/`.onnx` models | `Raspberry Pi/GUI/` | Historical/alternative model artifacts | File presence/hashes can be verified; authority and provenance mostly unverified | Already tracked; yes under current policy | Preserve for traceability; do not substitute for `bestv5.pt` without comparative validation |
| Gantry Nano USB alias | `/dev/arduino_gantry` resolving to `/dev/ttyUSB1`; udev topology rule `KERNELS=="3-2:1.0"` | Stable name used by `GTW_GUIv2.py` | Alias resolution verified for the current deployment | Sanitized rule/mapping: yes | Recreate topology rule only after matching the intended physical port; verify the alias resolves to the gantry without actuating it |
| Hydroponics Nano USB alias | `/dev/arduino_hydroponic` resolving to `/dev/ttyUSB0`; udev topology rule `KERNELS=="1-1:1.0"` | Stable name used by `GTW_GUIv2.py` | Alias resolution verified for the current deployment | Sanitized rule/mapping: yes | Recreate topology rule only after matching the intended physical port; verify the alias resolves to hydroponics without actuating it |
| Robotic-arm native UART | `/dev/ttyAMA1` in `Raspberry Pi/GUI/ServoControl.py` | 9600-baud Lobot binary action-group transport | Source path verified; legacy prototype arm actions previously worked through the deployed arrangement | Sanitized path/protocol fact: yes | Capture UART boot settings and wiring; validate any replacement/refactored arm client physically before use |
| Inactive robotic-arm udev alias | Rule requests `/dev/arduino_roboticarm` for topology `KERNELS=="1-2:1.0"` | Intended USB alias in retained udev evidence | Alias is currently absent and is not the active arm path | Sanitized rule/absence fact: yes | Do not treat as active or redirect code to it; investigate only with explicit hardware authorization |
| Wiring and electrical configuration | Schematics, harness labels, controller/relay/driver terminals | Physical connectivity, polarity, and safe limits | Unresolved/unverified in repository | Missing-status documentation: yes; guessed wiring: no | Obtain and physically validate wiring before hardware-affecting refactors |
| Sensor and pump calibration | Calibration records, solutions, sensor IDs, flow measurements | Convert measurements and dose durations into physical quantities | Active constants exist in source, but provenance/physical accuracy remain unresolved | Source and uncertainty: yes; invented calibration: no | Recalibrate with identified standards and record date, operator, raw data, and results |
| Arm action-group mapping | Arm controller storage plus `Arm Action File/*.rob` | Map GUI groups 1–6 to physical actions | GUI intent and prior prototype operation are known; exact deployed file/slot mapping remains unresolved | Existing `.rob` files and uncertainty: yes | Back up controller state and validate each action in a controlled clearance test before refactoring |
| Firmware build metadata | Arduino board/FQBN, toolchain, library versions, build options, flashed artifact hashes | Reproduce Gantry and Hydroponics Nano firmware | Unresolved/unverified | Missing-status documentation: yes; guessed build manifest: no | Capture from the verified build/deployment environment before compiling, uploading, or claiming reproducibility |

## Exact verified operator configurations

Console auto-login:

```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin growtechwall --noclear %I $TERM
```

Manual GUI startup:

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

USB topology rules retained as deployment evidence:

```udev
SUBSYSTEM=="tty", KERNELS=="3-2:1.0", SYMLINK+="arduino_gantry"
SUBSYSTEM=="tty", KERNELS=="1-1:1.0", SYMLINK+="arduino_hydroponic"
SUBSYSTEM=="tty", KERNELS=="1-2:1.0", SYMLINK+="arduino_roboticarm"
```

These udev rules bind physical USB topology, not board serial numbers. Current verified resolution is gantry `/dev/ttyUSB1`, hydroponics `/dev/ttyUSB0`, and no `/dev/arduino_roboticarm` alias. The arm uses native UART `/dev/ttyAMA1` in current source.

## Replacement-Pi validation boundary

Recreating files, packages, aliases, and service enablement is not sufficient to claim equivalent physical operation. Camera/display behavior, UART wiring, arm actions, Nano identity, sensors, calibration, relays, motors, pumps, and integrated workflows require separately authorized physical validation. Preserve unresolved items as unresolved until a test record exists.
