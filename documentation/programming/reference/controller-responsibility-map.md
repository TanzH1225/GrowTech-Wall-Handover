# Controller responsibility map

## Status and interpretation

This map records ownership established from the checked-in source. It does not establish wiring correctness, actuator polarity, calibration accuracy, or physical fault behavior. Those require recorded hardware validation.

## Architecture

The deployed system has four distinct endpoints. The robotic arm is not part of either Nano: the Raspberry Pi reaches its separate controller through the Pi native UART.

| Endpoint | Active Pi-facing path | Primary role |
|---|---|---|
| Raspberry Pi GUI/vision/coordinator | Local process | Operator UI, camera/YOLO, state display, and workflow coordination |
| Gantry Arduino Nano | `/dev/arduino_gantry` → `/dev/ttyUSB1` | Gantry motion, homing, endstops, and drivers |
| Hydroponics Arduino Nano | `/dev/arduino_hydroponic` → `/dev/ttyUSB0` | Sensors, RTC, lighting, water, and dosing outputs |
| Robotic-arm controller | Native UART `/dev/ttyAMA1` | Executes Lobot binary servo/action-group commands |

| Controller | Source-verified responsibilities | Explicitly not established as its responsibility |
|---|---|---|
| Raspberry Pi GUI/vision/coordinator | Tkinter UI and displayed state; USB-camera access; YOLO inference; captured-image storage; plant-position sequence; harvest/transplant/pesticide coordination; Nano serial clients; direct arm-controller command client; console and transient dashboard logging | Gantry step/dir output; gantry endstop acquisition; hydroponics sensor acquisition; hydroponics relay output |
| Gantry Arduino Nano | X, Y1, and Y2 `AccelStepper` control; stepper-driver enable outputs; X/Y homing; three endstops; grid coordinate conversion; relative motion; patrol; inactivity home/disable behavior; gantry serial parser and status text | Robotic-arm servos; hydroponics sensors or relays; camera/AI |
| Hydroponics Arduino Nano | DS3231 RTC; water-level, EC, and pH acquisition; EC/pH/water conversion; light schedule; water relay; fertilizer A+B, acid, and pesticide dosing; dosing timers; hydroponics serial parser and `STAT` output | Gantry movement; robotic-arm motion; camera/AI |
| Robotic-arm action controller via native UART | Executes binary servo/action-group commands sent by the Pi through `/dev/ttyAMA1` | Gantry movement and hydroponics control; its internal firmware and exact action-file loading process are not present in this repository |

## Detailed subsystem map

| Function/subsystem | Raspberry Pi | Gantry Nano | Hydroponics Nano | Arm controller | Evidence and qualification |
|---|---|---|---|---|---|
| GUI pages/widgets | Owns | — | — | — | `GTW_GUIv2.py` constructs four Tk tabs |
| GUI state and operator inputs | Owns | Reports motion state | Reports sensor/output state | No acknowledgement read | Pi state is not authoritative unless refreshed from a controller report |
| Camera and YOLO | Owns | — | — | — | OpenCV index `0`, Ultralytics `bestv5.pt` |
| Captured image storage | Owns | — | — | — | `~/plant_images/<plant>/<timestamp>.png` |
| Gantry motors and drivers | Commands | Owns | — | — | D2–D7 step/dir and A0–A2 enables in active gantry source |
| Homing and endstops | Requests/displays | Owns | — | — | D8–D10 active-low source configuration; physical wiring unverified |
| Grid coordinates | Mirrors 4×6 logical grid | Owns measured step arrays | — | — | Pi maps plant numbers; Nano maps row/column to motor steps |
| Robotic-arm motion | Chooses action group and timing | — | — | Executes | Pi sends Lobot binary frames over native UART `/dev/ttyAMA1`; legacy prototype groups previously worked, but refactored control requires new physical validation |
| Water/EC/pH acquisition | Displays | — | Owns | — | A0/A1/A2 in timestamped hydroponics source |
| Sensor calibration math | Does not calculate | — | Owns | — | Embedded constants; provenance and accuracy unverified |
| Main water pump | Commands desired state | — | Owns relay | — | D5, documented NC/active-low in source |
| Fertilizer A and B | Commands dose/target | — | Owns both relays and timer | — | D4/D3, activated together by current firmware |
| Phosphoric-acid pump | Commands dose/target | — | Owns relay and timer | — | D2; chemical identity follows project description, not a repository wiring record |
| Pesticide pump | Commands dose during workflow | — | Owns relay and timer | — | D10; source ignores pesticide-specific mL argument |
| Lighting | Commands state/schedule | — | Owns relay and RTC schedule | — | D9, documented NC/active-low in source |
| Plant scan sequence | Owns | Executes requested positions | — | May run idle group | Pi snake-order automation |
| Harvest/transplant workflow | Owns coordination | Executes requested positions | — | Executes groups 1–5 | Group-to-physical-action mapping is inferred from GUI comments and requires validation |
| Pest workflow | Owns coordination | Holds position | Executes pesticide output | Executes group 6 | Timing alignment is assumed by fixed sleeps |
| Gantry failure handling | Parses some text; no transaction recovery | Homing timeout, blocking halt, inactivity behavior | — | — | No system-wide fault state |
| Hydro failure handling | Displays valid `STAT` lines only | — | Timed dose shutoff; halts if RTC missing | — | No sensor validity or water interlock in source |
| Persistent logging | Saves images only | None | None | Not known | Dashboard/console/serial messages are transient |

## Authority boundaries to preserve

- The Pi is a supervisor, not a replacement for Nano pin-level ownership.
- The arm controller is a fourth endpoint. Do not move its responsibilities into the gantry Nano without a separately approved physical redesign.
- `/dev/arduino_roboticarm` is currently absent and is not an active fifth endpoint or alternate arm path.
- Pi UI state must not be treated as proof that a controller accepted or completed a command.
- The hydroponics Nano's current autonomous dosing and light behavior continues independently of Pi UI state.
- A future shared state model should distinguish requested, transmitted, acknowledged, active, completed, failed, and unknown states. That is deferred future work, not verified legacy behavior.
