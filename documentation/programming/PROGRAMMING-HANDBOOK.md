# GrowTech Wall — Programming Handbook

**Edition: 8 November 2026**  
**Audience:** the programmer taking over the prototype, its Raspberry Pi application, both Arduino Nano programs, and robotic-arm integration.

**Project status:** discontinued and no longer actively maintained. The project is preserved as-is for study, software recovery and independent development.

This handbook explains how the project works, where to change it, how to recover the software, and what to check before operating modified code. Start here; use the linked technical chapters when you need a function-level trace or a complete protocol detail.

The documented source baseline before this documentation update is commit `f1ab759ebe517d81a11bb1b057cdfa5332a0a3fd`. The project owner has reported successful prototype operation of the application branch and both updated Nano programs. That is a real-use report; the exact running commit, uploaded binaries, individual test cases and fault-test results were not captured. This document describes the available source and recorded build context without treating a successful demonstration as a test of every failure condition.

The owner has now identified the arm board as the **Hiwonder Bus Servo Controller**, programmed with **Bus Servo Control V3.4.exe**. The Pi calls action groups already saved on that board. The [Hiwonder controller guide](09-hiwonder-arm-controller.html) adds the manufacturer documentation, PC workflow and development routes beyond stored actions.

## 1. What the software controls

GrowTech Wall combines a 24-position growing wall, an X/dual-Y gantry, a robotic arm, hydroponic monitoring and dosing, and camera-based plant classification. Four controllers have different responsibilities:

| Controller | Responsibility | Connection to the Pi |
|---|---|---|
| Raspberry Pi 5 | Touchscreen application, camera, YOLO inference, image storage and coordination of complete plant workflows | Supervisor |
| Gantry Arduino Nano | X, left Y1 and right Y2 stepper channels; switches, homing, grid positions and motor enables | USB serial, `/dev/arduino_gantry`, 9600 baud |
| Hydroponics Arduino Nano | Water level, EC, pH, RTC lighting, main water pump, fertilizer A+B, acid and pesticide outputs | USB serial, `/dev/arduino_hydroponic`, 9600 baud |
| Hiwonder Bus Servo Controller | Stored robotic-arm action sequences; manufacturer-supported servo control functions | Native UART, `/dev/ttyAMA1`, 9600 baud |

Neither Nano forwards arm commands. The Pi does not directly sample hydroponic sensors or drive the gantry step/direction pins. These boundaries are useful when diagnosing a fault: a working touchscreen does not establish that a Nano is receiving commands, and a serial write does not establish that an actuator moved.

```text
Touchscreen + Logitech USB webcam
                 |
          Raspberry Pi application --> Plant image folders
                 |
                 +-- USB text --> Gantry Nano --> X / Y1 / Y2
                 |                   ^
                 |                Home switches
                 |
                 +-- USB text --> Hydro Nano --> Pumps / lighting
                 |                   ^
                 |                Sensors / RTC
                 |
                 +-- UART binary --> Hiwonder board --> Arm servos
```

The owner identifies the webcam as a Logitech USB camera; the report names C920. The code selects camera index `0`, rather than checking its USB model or serial number. A Hailo AI HAT is visible in the electrical evidence, but this application uses the documented Ultralytics/Torch path; installed hardware alone does not establish that inference runs on the HAT.

## 2. Find the right program

The source includes the modular application for independent maintenance/development and the preserved operator entry point. Keep their filenames intact: scripts, recovery instructions and existing installations depend on them.

| Location | How to use it |
|---|---|
| [Raspberry Pi/GUI/refactored](../../source%20code/Raspberry%20Pi/GUI/refactored) | Main maintenance target for the modular Python application, simulation and tests. Start at `app.py`. The folder name is retained as an existing path. |
| [gantry_main_refactored](../../source%20code/gantry_main_refactored) | Modular gantry sketch and its matching configuration, motion and command files. |
| [NFT_Hydroponics_refactored](../../source%20code/NFT_Hydroponics_refactored) | Modular hydroponics sketch, controller and configuration. |
| Raspberry Pi/GUI/GTW_GUIv2.py | Preserved Pi operator entry point in the recorded manual-start procedure. It contains hardware initialization at top level. |
| Raspberry Pi/GUI/ServoControl.py | Preserved Hiwonder-compatible binary helper; opens UART when imported. Read it as text on a laptop. |
| gantry_main | Preserved gantry sketch with its `GantryController.h/.cpp`. |
| Timestamped hydroponics folder | Authoritative preserved hydroponics baseline for comparison and recovery. |
| [Arm Action File](../../source%20code/Arm%20Action%20File) | Local `.rob` action files. The Pi does not load these files; the board executes its stored slots. |
| [requirements-pi.txt](../../source%20code/requirements-pi.txt) | Direct Python dependency pins derived from the captured Pi environment. |
| [requirements-dev.txt](../../source%20code/requirements-dev.txt) | Dependency-free headless test environment declaration. |
| [docs/pi-deployment-manifest.md](reference/pi-deployment-manifest.html) | Pi storage, startup, aliases and recovery evidence. |

The root `NFT_Hydroponics/NFT_Hydroponics.ino` is an older, protocol-incompatible program. Do not select it because its filename looks simpler. `arduino_gui.py`, `ClockModule`, `LightStatus`, `Gantry System` and the historical `IDP` sketches are reference/experiment material rather than the current application composition. Retain them for traceability.

The owner's successful prototype report does not identify a replacement startup command. The recorded operator procedure therefore remains `GTW_GUIv2.py`; do not silently replace a launcher during documentation or a software-only change. The modular `app.py` has its own explicit startup route and requires the correct environment and operating checks before hardware use.

### Main Python files

All paths in this table are inside `Raspberry Pi/GUI/refactored/`.

| File or directory | Responsibility and best starting point |
|---|---|
| `app.py` | Argument parsing, platform check, provider construction and startup/shutdown. `--simulate` selects in-memory devices. |
| `config/settings.py` | Immutable defaults: ports, baud, model, camera, image folder, action-group waits and rack position. There is no external settings-file loader. |
| `domain/grid.py` | Plant numbers, GUI coordinates and gantry grid coordinates. |
| `domain/models.py` | Data objects for detection, vision results and hydroponic status. |
| `comm/protocols.py` | Pure command encoders and response parsers. Start here for exact wire formats. |
| `comm/line_parser.py` | Accumulates partial serial reads and emits complete lines. |
| `comm/serial_transport.py` | Explicit opening, locked writes, reads and closing of a serial endpoint. |
| `comm/clients.py` | Gantry, hydroponics and arm clients. Nano readers publish events; the arm client is currently write-only. |
| `services/controller.py` | `ApplicationController`: GUI-facing operations, ordering, reset, admission checks and lifecycle. |
| `services/state.py` | Requested and reported position, validity, freshness counters and ordered event routing. |
| `services/events.py` | Event envelopes and the queue read by the GUI. |
| `services/worker_lane.py` | FIFO worker queue for jobs that must run in order. |
| `services/workflows.py` | Harvest, transplant, pesticide and arm group coordination. |
| `services/automation.py` | Scan Only and Full Auto traversal and cancellation. |
| `vision/logic.py` | Pure ROI, candidate selection and image-path rules. |
| `vision/hardware.py` | Camera, model loading, inference, annotation and saved images. |
| `simulation/` | Fake controllers and deterministic vision. |
| `gui/main_window.py` | Four touchscreen tabs, dialogs, controls and main-thread event handling. |
| `tests/` | Standard-library unit tests with fake devices. |

For the complete symbol map, use [System and code map](01-system-and-code-map.html).

## 3. First session on a laptop

Read [AGENTS.md](reference/Repository-guidance.html) before executing repository code. The machine can home or move when application startup or a USB serial reopen resets a controller. A laptop review should use the modular simulation and fake-device tests.

Use Python 3.11 as the established development baseline. The recorded Windows test environment used Python 3.11.9; the captured Pi environment used Python 3.11.2. The headless test suite needs no third-party hardware or vision packages. A visible simulation additionally needs Tkinter.

From the repository root, the portable test workflow is:

```powershell
Set-Location 'Raspberry Pi/GUI/refactored'
python -B -m unittest discover -s tests -q
```

Review test isolation when working on a later revision. Existing tests inject fake serial transports, camera/model objects, controllers, clocks or GUI widgets. Never import `GTW_GUIv2.py` or `ServoControl.py` as a shortcut for obtaining functions. Syntax-only checks can parse source without executing it.

For a visible software-only demonstration:

```powershell
python -B app.py --simulate
```

Run it from the same application directory. Add `--verbose` when investigating logs. Omitting `--simulate` selects hardware mode, which checks for Linux/aarch64 and Raspberry Pi device-tree evidence before constructing real providers. That platform check does not establish the identity or readiness of attached equipment.

Simulation exercises navigation, event ordering, state handling and workflow choices. It does not reproduce switch timing, mechanics, sensor acquisition, pump flow, real image inference or servo motion. Mock gantry moves are immediate; mock vision produces deterministic labels and does not save production images. Do not use simulated performance as a cycle-time estimate.

The recorded 9 October 2026 headless run passed **89 tests**, with hardware imports and real Tk-window creation blocked. This is a dated result for the documented source. See the current release's verification record for any later run rather than assuming that result automatically applies to a changed checkout.

## 4. Pi installation and startup

The existing deployment uses a 116.5 GB SD card. Its boot partition is `/dev/mmcblk0p1` at `/boot/firmware`, and its root partition is `/dev/mmcblk0p2` at `/`. The `growtechwall` user auto-logs into console `tty1`. The GUI is then started manually; console login does not launch the application.

The recorded operator commands are:

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

These are hardware-operation commands. Opening the application initializes serial endpoints and camera resources, and a Nano reset can trigger homing. Use them only when the prototype is ready for operation.

The modular application starts from `Raspberry Pi/GUI/refactored/app.py`. Its hardware command is `python3 app.py` from that directory with the correct Pi environment active. Treat choosing that entry point as an explicit deployment decision: record the commit, environment and matching Nano programs, and retain the current launch procedure until the replacement has been checked on the machine.

### Dependencies and device identities

The captured environment is Debian 12 Bookworm/aarch64, Python 3.11.2. The proposed direct package pins are:

| Package | Recorded pin |
|---|---:|
| NumPy | 2.2.6 |
| Pillow | 11.2.1 |
| pyserial | 3.5 |
| opencv-python | 4.11.0.86 |
| Torch | 2.7.0 |
| torchvision | 0.22.0 |
| Ultralytics | 8.3.147 |

Tkinter is provided by the OS package `python3-tk`, rather than this pip file. The dependency list is a starting point for reproducing the old environment, not a freshly demonstrated installation on a replacement Pi. ARM wheel sources and resolved dependencies must be recorded during recovery. The modular vision service uses Ultralytics with `.pt` weights and has no ONNX fallback.

The recorded aliases resolve as follows:

| Application path | Recorded underlying device | Important detail |
|---|---|---|
| `/dev/arduino_gantry` | `/dev/ttyUSB1` | USB topology rule; verify after changing USB ports/hubs. |
| `/dev/arduino_hydroponic` | `/dev/ttyUSB0` | USB topology rule; do not identify a Nano by enumeration order alone. |
| `/dev/ttyAMA1` | Native Pi UART | Arm controller, independent of the Nano USB connections. |
| `/dev/arduino_roboticarm` | Absent | Retained historical rule; not the active arm connection. |

The owner-recorded arm harness is Pi physical pin 27/GPIO0/orange to controller RX, physical pin 28/GPIO1/purple from controller TX, and physical pin 25/grey ground. Keep this project-specific record separate from generic Pi UART examples. Reproduce the actual UART configuration and verify the physical connection before changing it; do not substitute physical pins 8/10 by assumption. See [Hiwonder integration](09-hiwonder-arm-controller.html) and the electrical handover for the interface detail.

SSH and Raspberry Pi Connect were enabled on the recorded system. Keep passwords, tokens, SSH keys and private disk images outside Git. Recover the Pi using the [deployment manifest](reference/pi-deployment-manifest.html) and [replacement-Pi guide](reference/new-pi-recovery.html); the older guide contains historical statements, so use the current requirements file and this handbook for the present source inventory.

## 5. How the application runs

The modular application constructs providers, starts them explicitly, builds the Tk window and runs the event loop. Startup attempts vision, arm, gantry and hydroponics independently; a failed endpoint produces an offline/error indication rather than silently switching to simulation. Shutdown is called from a `finally` block.

Tk owns widgets and GUI variables on the main thread. Worker code publishes events instead of manipulating widgets. The application uses four ordered worker queues:

| Queue | Work |
|---|---|
| Workflow | Manual motion and coordinated arm workflows, with ordering relative to capture. |
| Hydro | Hydroponics settings and commands. |
| Vision | Manual capture/model work. |
| Reset | Device-reset coordination. |

Automation has its own coordinator thread. `ApplicationEventRouter` updates state and queues the corresponding event in one ordered operation. The GUI drains up to 200 queued events every 50 ms by default. Keep new code behind these boundaries; direct calls from widgets to serial/camera resources bypass ordering and failure handling.

### Position is a report, not a button colour

`ApplicationState` distinguishes the requested grid coordinate from the reported coordinate. A new request invalidates the previous position. A fresh, matching `POS` advances a local generation counter and makes the coordinate usable. Capture, harvest and transplant use this state rather than reading a widget colour.

Generation counters belong to the Pi. The serial protocol has no transaction IDs, so they cannot identify a delayed same-coordinate response with certainty. Position and homing waits check cancellation but have no general completion deadline. A missing report can therefore leave an operation pending until Stop, reset or shutdown releases the relevant wait.

Relative moves do not return `POS`, so sending a jog is not enough to re-establish a selected plant. Select a grid coordinate and receive a fresh report before a position-dependent operation.

### Operator controls

| Tab/control | What it does |
|---|---|
| Dashboard | Displays latest operating information and vision result. |
| Gantry & Arm | Grid selection, jog, home/disable, capture and arm workflows. |
| Hydroponic | Sensor display, water/light controls, manual dosing, targets, lighting hours and automatic dose setting. |
| Vision | 24 plant positions and their latest result labels; its position buttons request movement. |
| Auto: Scan Only | Moves through the wall and captures results without classification-triggered harvesting or spraying. |
| Auto: Full Auto | Moves, captures and dispatches arm/dosing workflows according to the label policy. |
| Stop | Requests cancellation of Pi orchestration. It does not immediately halt an already-running Nano move or arm action. |
| Reset Devices | Coordinates Nano serial and vision recovery. The arm connection is not reset by this operation. |

Water/light buttons and setting labels can show requested state before any device response. `STAT` subsequently reconciles the output indicators, but it does not echo configured targets or schedules. A `Sent:` log means the transport write returned; it is not an acknowledgement from the hardware.

Reset invalidates position, prevents new endpoint jobs, advances a reset epoch and waits for queued work to quiesce. The two-second limit applies to that preparation, not the entire reset: model loading, serial reopening and Nano settling can take longer. Endpoints that do not close cleanly remain offline. Read the individual errors rather than relying on the common completion message.

## 6. Grid and complete plant workflows

The growing wall has six columns and four rows. Nano coordinates are one-based; GUI array rows run from top to bottom:

| Physical/grid row | Plant numbers left to right | Nano Y |
|---|---|---:|
| Top | 19, 20, 21, 22, 23, 24 | 4 |
| Third from bottom | 13, 14, 15, 16, 17, 18 | 3 |
| Second from bottom | 7, 8, 9, 10, 11, 12 | 2 |
| Bottom | 1, 2, 3, 4, 5, 6 | 1 |

`plant = (y - 1) * 6 + x`; GUI row is `4 - y`, GUI column is `x - 1`. Plant 8 is `(2,2)`, not a displacement in millimetres. The automatic snake order is **1–6, 12–7, 13–18, 24–19**. The seedling rack position in configuration is plant 6, `(6,1)`.

A normal grid selection sends `<x> <y>`, observes `START x y`, waits for a matching `POS x y`, then permits capture. Capture rechecks state and ordering before reading the camera. The Nano translates grid coordinates into measured step targets rather than using a uniform spacing formula.

### Current arm group intentions

The following table describes application calls. The manufacturer software assigns a chosen action file to a board slot; similarly named repository files do not by themselves prove the content currently installed in each slot.

| Group | Application meaning | Fixed Pi wait |
|---:|---|---:|
| 1 | Harvest pickup | 4 s |
| 2 | Rotate/store in basket | 4 s |
| 3 | Pick seedling from rack | 5 s |
| 4 | Plant seedling | 7 s |
| 5 | Idle/camera pose | 1 s |
| 6 | Pesticide arm action | 10 s |

**Harvest:** start from a valid grid report, run group 1, wait 0.5 s, then group 2. At column 1, move temporarily to column 2 on the same row for group 2 and return afterwards. Wait 1 s and run group 5.

**Transplant:** retain the original coordinate, move to the rack at `(6,1)`, run group 3, return to the original coordinate, run group 4, wait 0.5 s, then group 5.

**Pesticide:** send `DOSE:PEST:11` to the hydroponics Nano, run group 6, wait 0.5 s, then group 5. The Nano currently ignores the numeric PEST amount when choosing duration and uses its global dose-time setting. The value 11 is therefore a preserved command field, not a measured 11 mL delivery.

**Full Auto:** home, traverse each snake position, await its report, capture, and select one of these branches in order:

| Classification test | Action |
|---|---|
| Exactly `No detection`, or contains `Immatured` | Group 5. |
| Contains `Matured` | Harvest, then transplant unless cancelled. |
| Any other label | Pesticide workflow. |

These tests are case-sensitive. A new model label can unintentionally fall into the pesticide branch. Label policy and model replacement must therefore be reviewed together.

The arm waits are assumptions used by the Pi, not measured completion feedback. Cancellation can interrupt the Pi wait while the board continues the action already sent. The current modular arm-failure policy catches expected `GrowTechError` failures, warns, skips the unavailable group and lets its containing sequence continue. Other exception types can still fail the workflow. Do not interpret a returned workflow or a GUI “complete” outcome as independent confirmation of every physical step.

The preserved `GTW_GUIv2.py` also contains a later same-coordinate gantry refresh before most arm-group calls, with a 45-second matching-`POS` gate. Pesticide performs a separate position check before dosing and then runs group 6 without another refresh. Those gates are absent from the modular workflow. This is a material difference to consider when selecting or extending an entry point, particularly because gantry inactivity can initiate homing. It is documented here rather than silently changed.

## 7. Serial contracts

All three host links use 9600 baud. Nano commands are text terminated by one LF newline. Arm commands are binary packets beginning `55 55`. Do not send text group numbers to the arm or binary arm packets to a Nano.

Each Nano client buffers arbitrary serial chunks until a complete line is available. One USB read may contain a fragment, several records or both. The transport locks writes per endpoint, but the protocols still lack request IDs, retries, duplicate suppression and correlated command acknowledgements.

### Gantry quick reference

| Command before newline | Meaning | Completion behaviour |
|---|---|---|
| `3 2` | Move to column 3, row 2 | `START 3 2`, then `POS 3 2`. |
| `0 0` | Home all axes | `Homing complete.`; no grid `POS`. |
| `U`, `D`, `L`, `R` | 10 mm relative jog in the selected direction | Descriptive text; no `POS`. |
| `G` | Next plant in snake order | `START` may be printed twice, then `POS`. |
| `O` | Home dual Y, then disable motor drivers | `Motors disabled.`; this is not an immediate stop. |
| `P` | Firmware patrol | Checks serial between blocking moves. |
| `X` | Leave firmware patrol | Only consumed as a stop within patrol; not a general motion-stop command. |

The modular Pi accepts fresh `Homing complete.` to finish a home wait. Homing establishes mechanical zero; it does not create a selected plant for capture. Normal `POS` reports mean the firmware's step loops reached their targets; there is no independent continuous position measurement.

### Hydroponics quick reference

| Command | Meaning |
|---|---|
| `WATER_PUMP:ON` / `WATER_PUMP:OFF` | Set main water output. |
| `LIGHT:ON` / `LIGHT:OFF` | Set light and enable manual override. |
| `DOSE:FERT:<mL>` | Run fertilizer A and B together. |
| `DOSE:ACID:<mL>` | Run acid output. |
| `DOSE:PEST:<mL>` | Run pesticide output using the global duration, regardless of the supplied amount. |
| `TARGET_EC:<value>` | Positive value enables automatic EC dosing; nonpositive disables future starts. |
| `TARGET_PH:<value>` | Positive value enables automatic pH dosing; nonpositive disables future starts. |
| `LIGHT_ON_HOUR:<0..23>` / `LIGHT_OFF_HOUR:<0..23>` | Change schedule and clear light manual override. |
| `DOSE_TIME:<value>` | Set global duration through the source's 1000 ms per requested mL conversion. |

The controller sends this status layout approximately every second:

```text
STAT,<millis>,<water-percent>,<ec>,<ph>,<light>,<water-pump>,<acid>,<fertilizer>,<pesticide>
```

The final five fields are `0`/`1`. The fertilizer field covers A+B together. `millis` is controller uptime, not RTC clock time. The Pi presents EC as µS/cm, while the transmitted field has no unit suffix. A flag describes the controller's logical/output state, not proof of liquid flow.

The Pi parser accepts the ten-field prefix plus extra trailing fields. It validates field shape, but does not reject all physically implausible sensor values or floating-point `NaN`/infinity. A valid parse is not sensor-health validation.

For exact builders, framing, byte examples and response handling, use [Communications](03-communications.html). For the manufacturer arm protocol and future direct control, use [Hiwonder controller guide](09-hiwonder-arm-controller.html).

## 8. Gantry firmware

The gantry sketch delegates command interpretation to `GantryCommandProcessor` and physical step generation to `GantryMotion`. `GantryConfig` contains the fixed pin, speed, timing and grid constants. Keep the full sketch folder together when building; copying only its `.ino` is insufficient.

### Pin contract

| Channel | STEP | DIR | Enable | Home switch |
|---|---|---|---|---|
| X | D2 | D3 | A0 | D8 |
| Y1, left when facing the machine | D4 | D5 | A1 | D9 |
| Y2, right | D6 | D7 | A2 | D10 |

Enable outputs are LOW to enable and HIGH to disable. Switch inputs use `INPUT_PULLUP` and LOW assertion. X and Y1 direction inversion differ from Y2 in source. Preserve that relationship when tracing a replacement driver or comparing firmware.

### Motion configuration

| Setting | Source value |
|---|---:|
| X conversion | 40 steps/mm |
| Y conversion | 26.667 steps/mm |
| Configured travel speed | 300 mm/s |
| Acceleration | 5000 steps/s² |
| Fast / slow home | 75 / 10 mm/s |
| Bump retract | 10 mm |
| Approach timeout | 15,000 ms per fast/slow approach |
| Switch debounce | 50 ms |
| Startup delay | 2000 ms |
| Inactivity timeout | 60,000 ms |
| Move / home settling | 200 / 100 ms |

These are program settings, not measured achievable speeds or certified limits. The firmware uses these X targets in steps from home:

| Y row | X1 | X2 | X3 | X4 | X5 | X6 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 900 | 5980 | 11100 | 16100 | 21220 | 26520 |
| 2 | 900 | 5980 | 11100 | 16100 | 21220 | 26520 |
| 3 | 900 | 6280 | 11300 | 16100 | 21520 | 26520 |
| 4 | 900 | 5980 | 11100 | 16100 | 21220 | 26520 |

Y targets are `0, 6800, 13600, 18934`. Row 3 deliberately differs. Do not replace the table with an evenly spaced calculation. The preserved bounds are X `0..28200`, Y `0..28800`; the Y maximum formula uses 40 rather than the normal Y conversion factor. That inconsistency is an existing behaviour, not an invitation to correct a number without travel validation.

Homing runs X first, then dual Y. Each approach moves negative toward the switch, confirms LOW, retracts, approaches slowly and zeros the step counters. Dual Y stops scheduling each side's approach pulses independently as it reaches its own switch. The modular firmware stops an axis's scheduled motion at the initial LOW edge while confirming debounce; it also explicitly disables drivers on a homing fault and then halts. The preserved firmware has different fault/debounce details.

Normal moves and homing are blocking. Serial commands cannot interrupt them mid-loop. Bump retract has no timeout, normal movement does not continuously check switches, and software cannot process a command after the permanent fault halt. A nonempty command received while disabled can enable and home the machine before the command itself is validated. Inactivity also homes before disabling.

The owner reports that removing actuator power allows the vertical gantry to drop immediately. This matters to software maintenance: GUI Stop, `O`, a firmware fault and the physical E-stop are different operations. Do not treat driver-disable code as a guaranteed safe hold or recommend using a power cut as routine software reset.

For algorithms and source-level differences, see [Controller firmware](04-controller-firmware.html).

## 9. Hydroponics firmware

The hydroponics Nano owns its DS3231 RTC and performs the sensor calculations locally. `HydroponicsConfig.h` contains pins, constants and defaults. `HydroponicsController.cpp` implements acquisition, output timing, lighting, serial commands and status.

| Function | Nano pin | Requested-on level |
|---|---|---|
| Acid | D2 | HIGH |
| Fertilizer B | D3 | HIGH |
| Fertilizer A | D4 | HIGH |
| Main water | D5 | LOW |
| Lighting relay | D9 | LOW |
| Pesticide | D10 | HIGH |
| Water-level sensor | A0 | Analog input |
| EC sensor | A1 | Analog input |
| pH sensor | A2 | Analog input |
| RTC SDA / SCL | A4 / A5 | I²C |

The table describes code levels. Relay terminal arrangements and load polarity must be checked against the electrical records when servicing a real connection. The RTC is in the main electrical enclosure. The latest owner correction assigns lighting-relay logic power to the hydro Nano's 5 V, with D9 as its signal; this does not change the firmware pin assignment.

At startup, the controller writes pump-off states, blinks the light twice, initializes the RTC and calculates calibration coefficients. `RTC missing!` halts the program. If the RTC reports lost power, firmware sets it from the firmware build date/time; the Pi does not automatically synchronize it.

Defaults after reset are a five-second global dose, lighting on from hour 07 inclusive to 19 exclusive, automatic EC/pH control disabled and targets zero. Settings live in RAM and revert on reset. The schedule expression supports a same-day interval; an overnight setting such as on 19/off 7 does not work as a wraparound interval. Manual light override persists until a valid schedule-setting command or a reset.

Each update checks timed shutoffs, lighting, EC auto dosing, pH auto dosing, status and finally one serial command. EC and pH each have an independent ten-minute automatic-dose cooldown measured from start. Fertilizer runs when EC is below its enabled target; acid runs when pH is above its enabled target. These checks can overlap with each other and with pesticide.

Positive manual ACID/FERT volume requests use `mL * 1000` milliseconds; an already-active channel ignores a new request. The one-mL-per-second conversion is an assumption in software. It is not a pump calibration. Manual dosing does not restart the automatic cooldown, so an automatic dose can follow a manual one if the conditions permit. Changing `DOSE_TIME` can affect an active dose that uses the global duration. Disabling a target prevents later automatic starts but does not immediately terminate the active dose.

### Sensor calculations to preserve

| Sensor | Current calculation |
|---|---|
| EC | Linear anchors: ADC 64 → 84, ADC 439 → 12880, with lower clamp at zero. |
| pH | 100 ADC readings with 1 ms delays; sort, discard 20 high and 20 low readings, average the remaining 60; assume 5000 mV/1024 conversion; use the stored piecewise calibration and clamp to 0–14. |
| Water level | Cubic: `2.30841033e-5*r³ - 1.37886629e-2*r² + 2.74150783*r - 92.9694804`, clamped to 0–100%. |

The pH constants use 2773 mV at pH 4.00, 2275 at 6.86 and 1889 at 9.18. Preserve the actual branch/slope pairing in `readPh()`; the source's two slopes are applied in a way that does not exactly reproduce both named outer endpoints. Treat a correction as a calibration change requiring measured evidence. The separate calibration sketches have different pins/constants and must not silently replace the active controller configuration.

Timer shutoffs are cooperative. The pH sampling/sorting and an incomplete serial line can delay the next update; exact output-on time is not a hard real-time guarantee. Firmware has no water-presence interlock, sensor plausibility gate, chemical mutual-exclusion rule, maximum cumulative dose or immediate chemical-stop command. These limitations belong in requirements for future process-control work.

## 10. Camera, model and image records

The active model is `Raspberry Pi/GUI/bestv5.pt`. The recorded SHA-256 is:

```text
87c36a815ee6a0efdde2bcb71bec5b6cb1b8855a4958646df56f4afdc8ef9f19
```

Keep the exact model when reproducing current behaviour. Other `.pt` and `.onnx` files are historical alternatives; a larger version-like number does not prove a better or compatible model. `bestv3.pt` is byte-identical to the recorded `bestv5.pt`, but preserve both original names in the source archive.

The modular hardware service loads the model, opens camera index 0 and requests 640 × 640 frames. It waits 0.2 s, discards five camera grabs, then reads a frame. The requested resolution is not necessarily the delivered resolution.

Inference uses the complete RGB image. The region of interest is a subsequent detection-selection rule: a candidate's horizontal centre must fall between one-sixth and five-sixths of the frame width. This is the central **two-thirds**, with no vertical restriction. The highest-confidence eligible candidate at confidence at least 0.3 wins; ties preserve the first eligible candidate. The complete box need not lie inside the ROI.

The service draws the ROI and selected detection and saves an annotated PNG at:

```text
~/plant_images/<plant-number>/<YYYYmmdd_HHMMSS>.png
```

The output is not a raw training-image archive. Filenames have one-second resolution, so repeated captures for the same plant within one second can overwrite. No automatic retention or disk cleanup is implemented. Back up valuable image evidence separately from Git and monitor available space.

Model/camera startup errors, failed final frame reads and image-save failures reach the operation-error path. Inference or box-iteration exceptions are caught and logged; they can still produce an ordinary saved result, including `No detection` or a candidate accumulated before the error. A `No detection` label therefore does not prove healthy inference. Read logs when evaluating a run.

The repository now also contains dataset metadata under `IDP V2/GrowTechWall.v1i.folder/`. It identifies the [GrowTechWall Roboflow project](https://universe.roboflow.com/tan-wvn2v/growtechwall), a version 1 export from 11 May 2025, CC BY 4.0, 2349 images, folder-format annotations and 640 × 640 preprocessing with augmentation. This is useful provenance for that export. It does not establish a training chain from that folder export to the active `bestv5.pt` detection model. The [reference and asset guide](10-reference-context-and-assets.html) retains these metadata and explains the report context. Earlier statements that no dataset provenance exists should be read with this newer evidence.

Before replacing a model, complete the link between its weights, class map, training dataset/run, metrics and export details; compare a fixed set of real camera images against the current model. Check the Full Auto label rules as part of that change. Changing ROI, confidence, preprocessing, camera placement or label spelling changes system behaviour even if the GUI still looks the same.

## 11. Maintaining and extending the Hiwonder arm

The current project uses preprogrammed groups: **PC software prepares actions → the controller stores them → the Pi selects a group by UART**. The `.rob` files in Git are local programming assets, while board slots are live controller state. Git alone cannot prove which file/version currently occupies a slot.

The owner confirms **Bus Servo Control V3.4.exe** as the PC program. Obtain software and drivers through the official [Hiwonder Appendix](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/Appendix.html), and use the [Bus Servo Controller manual](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/1.Bus_Servo_Controller_User_Manual.html) for its interface and action editing. Links are supplied instead of redistributing the executable. The installed board and software confirmation closes the previous “controller/tool identity unknown” gap; servo IDs, live action-slot contents and board firmware identity still require a recorded inventory.

For a newcomer, use the dedicated [Hiwonder controller guide](09-hiwonder-arm-controller.html) before editing board actions. It covers the current group-call route, PC saving/downloading, manufacturer protocol references and the possible move toward direct servo targets and feedback. That future capability is separate from what the current GUI implements.

A practical extension should preserve one owner for the arm serial connection, put encoders/parsers under `comm`, expose a provider interface, coordinate motion through services and publish feedback events to the GUI. Begin with fake-transport fixtures, including fragmented responses and timeouts, rather than adding serial writes inside button callbacks. Define servo IDs, permitted ranges, speed/time policy, group/direct-control arbitration and completion/failure semantics before allowing autonomous targets. Physical clearance and servo limits must be validated on the actual arm; a manufacturer demonstration coordinate is not a safe pose for this prototype.

The controller has a local power switch. The owner reports that OFF removes arm operation and ON lights the controller enclosure. The gripper/joint chain uses yellow/red/black wiring and the base servo has a separate three-black-wire connection. Those colours alone do not determine servo IDs, controller sockets or electrical levels. Use the electrical handover before rewiring.

## 12. Troubleshooting from symptoms

Start with endpoint state, raw received text, the parsed event, and the application state. Each answers a different question. Avoid using actuator commands as a first device-identification test.

| Symptom | First checks and relevant source |
|---|---|
| GUI will not start on the Pi | Confirm working directory, selected entry point, active environment, Tk display session, model file and dependency import error. Read `app.py`, `config/settings.py` and the Pi environment record. |
| A Nano is offline | Verify USB identity/alias and permissions; inspect connection/read errors. Do not swap gantry and hydro aliases to make an error disappear. |
| Motion wait never finishes | Inspect missing/mismatched `POS`, home text, invalid state and firmware fault output. `services/state.py` waits have no general deadline. |
| Grid remains invalid after jogging/home | Expected: relative movement/home does not create a grid `POS`. Request a valid grid position during a controlled operating session. |
| Hydro readings stop | Check endpoint reader, complete-line framing and malformed `STAT` text before investigating sensor values. |
| Hydro value is implausible | Inspect raw ADC/calibration and sensor condition; valid text parsing is not physical plausibility checking. |
| Light schedule is wrong | Check RTC date/time, reset/defaults, manual override, and whether an unsupported overnight interval was configured. |
| Dosing duration does not match amount | Check source conversion, global dose setting, PEST special case, sampling/serial delays and actual measured pump flow. |
| Arm action is skipped while workflow progresses | Read warning events and current arm-failure policy. Confirm local controller switch, UART identity and installed slot. |
| Arm acts from an unexpected gantry condition | Check inactivity homing and the entry-point difference in per-group position refresh. |
| No detection after a model error | Inspect logs; `capture()` can convert an inference exception into an ordinary result. |
| Reset completes but a device remains offline | Read per-endpoint reset results; the common message does not establish successful reopening of every provider. |
| Images are missing/overwritten | Check permissions, free space, configured image root, failed writes and same-second filenames. |

Do not run two application instances or a separate terminal/controller tool against the same interface during operation. Record which tool owns a connection when changing between PC action editing and Pi control.

## 13. Change, release and recovery workflow

1. Record the repository commit and known local changes. Read the affected source and its protocol/configuration contract.
2. Choose a small boundary: UI, domain logic, parser, transport, workflow, firmware or vision. Capture representative inputs/outputs before changing it.
3. Keep hardware initialization explicit and use fake devices for laptop work. Add meaningful regression cases for the behaviour being changed.
4. Run relevant existing tests, then review the diff for altered ports, command bytes, pins, active levels, timing, step arrays, model selection, labels and startup paths.
5. Preserve a known-good software/firmware/action backup. Record dependencies, controller build settings and asset hashes before an upload or replacement.
6. Validate hardware-affecting changes in controlled stages on the identified prototype. Record date, operator, hardware state, software/firmware identity, procedure, expected and observed results.
7. Merge a behaviour-changing phase to `main` only after its required physical checks pass. Documentation publication alone does not deploy code to the Pi or a controller.

Firmware depends on Arduino core APIs, `AccelStepper` for gantry and `Wire`/`RTClib` for hydroponics. The precise Nano processor/bootloader selection, board package/compiler and library versions are not captured sufficiently for a reproducible flash image. Do not guess an old/new bootloader option and describe the resulting binary as the deployed build. Record those values from the working setup before upgrading tools or uploading.

For Pi recovery, retain the repository, active model, reviewed package/deployment records, udev/UART/display configuration and approved action files. Maintain any full SD-card image in private controlled storage, outside Git. A ZIP of source/resources is a handover package, not a complete machine image or proof that restoring files reproduces every live setting.

### Priority work for the next programmer

| Priority | Concrete task |
|---|---|
| Before the next deployment | Record the actual Pi launcher/commit, Nano build/upload settings and installed Hiwonder slot/servo inventory. |
| Before changing arm workflows | Resolve the entry-point differences in gantry refresh, pesticide position gating and failure continuation; establish actual completion handling. |
| Before extending automatic dosing | Define sensor-fault, water-presence, dosing-limit and chemical-coordination requirements using calibrated measurements. |
| Before unattended operation | Define bounded waits, disconnect/restart handling and physical stop behaviour across all controllers. |
| Before model replacement | Preserve current weights and compare labelled real-camera cases; verify class-to-action policy. |
| For maintainability | Add durable event records and reproducible build/dependency manifests without storing credentials or private machine images. |

These items are engineering follow-up, not hidden repairs performed by this handover. The source, existing operating knowledge and manufacturer development references are available for the next person to make deliberate changes.

## 14. Reference map

| Need | Reference |
|---|---|
| Function-level source navigation | [01 — System and code map](01-system-and-code-map.html) |
| GUI lifecycle, queues, reset and workflow traces | [02 — Pi application](02-pi-application.html) |
| Exact text/binary contracts and framing | [03 — Communications](03-communications.html) |
| Complete controller algorithms and calibration mathematics | [04 — Controller firmware](04-controller-firmware.html) |
| Model/action inventories and detailed vision behaviour | [05 — Vision and assets](05-vision-and-assets.html) |
| Test isolation and recovery detail | [06 — Development, testing and recovery](06-development-testing-and-recovery.html) |
| Detailed programming backlog | [07 — Maintenance and open issues](07-maintenance-and-open-issues.html) |
| Earlier source inspection and verification record | [08 — Evidence and change record](08-evidence-and-change-record.html) |
| Hiwonder software, controller protocol and future control | [09 — Hiwonder arm controller](09-hiwonder-arm-controller.html) |
| Report context, dataset metadata and packaged assets | [10 — Reference context and assets](10-reference-context-and-assets.html) |
| Pi operating/recovery facts | [Deployment manifest](reference/pi-deployment-manifest.html), [Pi environment](reference/pi-environment.html) |
| Owner's successful prototype report | [Prototype test confirmation](reference/prototype-test-confirmation.html) |

The earlier technical chapters retain their dated inspection history. This handbook and the new Hiwonder chapter provide the newcomer-facing entry point and latest owner identification. Where older text says the arm controller or PC tool is unknown, the owner's Hiwonder/Bus Servo Control V3.4 confirmation supersedes that particular gap; it does not determine live slot contents, servo IDs or physical test results.
