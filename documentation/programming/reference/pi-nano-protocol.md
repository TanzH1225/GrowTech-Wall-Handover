# Pi-to-controller communication protocol

## Document status

This document is a source-derived protocol baseline. No live serial traffic was generated while producing it. Port identities, physical USB placement, controller firmware actually flashed, electrical behavior, and timing under load require physical validation.

## Communication overview

| Path | Pi device | Settings | Framing | Current acknowledgement model |
|---|---|---|---|---|
| Pi to gantry Nano | `/dev/arduino_gantry` → `/dev/ttyUSB1` | 9600 baud, Pi read timeout 1 second | UTF-8/ASCII text terminated by newline | Asynchronous text such as `START` and `POS`; no command ID or correlated ACK |
| Pi to hydroponics Nano | `/dev/arduino_hydroponic` → `/dev/ttyUSB0` | 9600 baud, Pi timeout `None` | UTF-8/ASCII text terminated by newline | Periodic `STAT` only; no correlated command ACK |
| Pi to robotic-arm controller | Native UART `/dev/ttyAMA1` in `ServoControl.py` | 9600 baud | Lobot binary frames beginning `0x55 0x55` | Write-only in current Pi code; no response read |

The active Pi source does not use GPIO, Pi I2C, or another bus to control the Nanos. The hydroponics Nano itself uses I2C internally for its RTC.

## Verified deployed device resolution

The current deployment resolves:

```text
/dev/arduino_gantry      -> /dev/ttyUSB1
/dev/arduino_hydroponic  -> /dev/ttyUSB0
```

Both aliases come from udev rules that match physical USB topology (`KERNELS=="3-2:1.0"` and `KERNELS=="1-1:1.0"`). They are not board-serial-number mappings. USB port, hub, or enumeration changes can invalidate the association, so replacement-Pi recovery must confirm endpoint identity without sending actuator commands.

`ServoControl.py` does not use a USB alias. It opens the Pi native UART `/dev/ttyAMA1`. Although the retained udev evidence includes a rule that could request `/dev/arduino_roboticarm`, that alias is currently absent and must not be treated as an active arm endpoint.

## Pi-to-gantry protocol

### Connection lifecycle

`GTW_GUIv2.py` opens `/dev/arduino_gantry` with `serial.Serial(..., 9600, timeout=1)`, sleeps two seconds, and resets input and output buffers. Opening a USB serial Nano can reset it; the exact deployed USB bridge/reset behavior is not captured. The active firmware starts serial at 9600, waits for serial, delays two seconds, and immediately homes all axes.

### Commands accepted by the gantry firmware

| Command | Meaning in current firmware | Current GUI use | Completion/status behavior |
|---|---|---|---|
| `0 0` | Re-home all axes and zero positions | Home and automation startup | Emits homing text but no `POS`; this is incompatible with the full-auto reached wait |
| `<col> <row>` | Move to column 1–6, row 1–4 | Grid buttons and automation | Emits `START <col> <row>`, then `POS <col> <row>` |
| `U` | Move Y +10 mm | Manual Up | Text only; no `POS` |
| `D` | Move Y -10 mm | Manual Down | Text only; no `POS` |
| `L` | Move X -10 mm | Manual Left | Text only; no `POS` |
| `R` | Move X +10 mm | Manual Right | Text only; no `POS` |
| `G` | Advance to next snake-grid position | Manual Next | Emits `START` and then `POS` through the grid move |
| `O` | Home dual Y, then disable drivers | GUI Disable | Emits descriptive text and `Motors disabled.`; it is not an immediate stop |
| `P` | Run complete firmware patrol | Not used by active GUI | Patrol checks for `X` only between blocking position moves |
| `X` | Stop a running patrol at its next serial check | Not sent by active GUI | Does not interrupt a normal grid/relative/homing operation |

Invalid coordinates report `Error: Grid coordinates out of range.` Other invalid formats or single characters report descriptive error text.

### Responses consumed by the Pi

| Response pattern | Pi interpretation |
|---|---|
| `START <x> <y>` | Marks the corresponding UI target as moving |
| `POS <x> <y>` | Marks reached, updates grid/plant position, and releases some workflow waits |
| `STATE ...` | Sets textual gantry state; current firmware does not appear to emit this prefix |
| `TIMEOUT:...` | Shows timeout/homing-disable state |
| Text containing `Motors disabled` | Shows disabled state |
| Other homing/error text | Displayed as raw gantry text but not converted into a structured workflow failure |

The patrol implementation can emit duplicate `START` records because both `patrolGrid()` and `goToGridPosition()` print one.

### Gantry timeout and interruption limitations

- Pi writes have no lock, sequence number, acknowledgement deadline, retry, or duplicate suppression.
- Automation waits have no completion deadline.
- The Nano performs motion in blocking loops and normally cannot parse a new command until motion completes.
- The Pi's automation stop event cannot interrupt active Nano motion.
- After sixty seconds without a processed command, the Nano initiates homing and then disables motors. This is movement, not a passive safe stop.
- Reopening the serial port can reset the controller and initiate startup homing.

## Pi-to-hydroponics protocol

### Connection lifecycle and status framing

The Pi opens `/dev/arduino_hydroponic` at 9600 baud with timeout `None`, waits two seconds, and resets buffers. The Nano emits once per second:

```text
STAT,<millis>,<water-percent>,<ec>,<ph>,<light>,<water-pump>,<acid>,<fert>,<pesticide>
```

Boolean fields use `1` or `0`. The Pi parses water, EC, pH, light, water pump, acid, and fertilizer. It does not expose the pesticide field in `update_hydro_ui()`.

The current reader requests `in_waiting or 1` bytes and passes each returned chunk directly to the line parser. It has no hydro-specific partial-line buffer. A fragmented record or multiple records in one chunk can therefore be dropped.

### Commands accepted by the timestamped firmware

| Command | Source-verified effect | Validation/response limitation |
|---|---|---|
| `WATER_PUMP:ON` / `OFF` | Sets D5 active-low relay | Any value other than `ON` becomes off; no ACK |
| `LIGHT:ON` / `OFF` | Sets D9 and enables manual override | Any value other than `ON` becomes off; no ACK |
| `DOSE:ACID:<mL>` | Starts acid for `mL * 1000` ms | No maximum or correlated completion response |
| `DOSE:FERT:<mL>` | Starts fertilizer A and B together | No maximum or correlated completion response |
| `DOSE:PEST:<mL>` | Starts pesticide | `<mL>` is parsed but ignored; duration uses global `doseTimeMs` |
| `TARGET_EC:<value>` | Enables EC auto-dose when value > 0 | No upper/plausibility bound or ACK |
| `TARGET_PH:<value>` | Enables pH auto-dose when value > 0 | No upper/plausibility bound or ACK |
| `LIGHT_ON_HOUR:<0..23>` | Updates scheduled on hour; clears manual override | Invalid hour ignored silently |
| `LIGHT_OFF_HOUR:<0..23>` | Updates scheduled off hour; clears manual override | Invalid hour ignored silently |
| `DOSE_TIME:<mL>` | Sets default duration to `mL * 1000` ms | Affects auto doses and pesticide; no upper bound or ACK |

Settings exist only in RAM and revert on reset. The Pi optimistically changes some displayed toggle state immediately after sending; periodic `STAT` later becomes the closest available source of controller state.

### Hydroponics failure behavior

- Serial loss does not stop an already active timed dose; the Nano loop is intended to turn it off at the local deadline.
- Serial loss does not automatically turn off the water pump or light.
- A Nano hang, power/output-stage fault, or blocked loop during an active output is not safely characterized by repository evidence.
- Sensor disconnection or implausible readings are not explicitly detected before automatic dosing.
- Acid and fertilizer automation are independent and can be active concurrently according to source.
- There is no water-level interlock for chemical dosing.

## Pi-to-robotic-arm path

`ServoControl.py` opens the native UART `/dev/ttyAMA1` at 9600 baud during import. It builds binary frames with header `0x55 0x55`, a length byte, command byte, and command-specific data. It supports individual/multiple bus or PWM servo moves, action-group run/stop, and group speed. The active GUI uses action-group run with groups 1–6 and assumes completion using fixed sleeps of 1–10 seconds.

The repository does not contain the arm controller firmware or a verified mapping between every `.rob` file, board slot, and GUI group number. Comments in the GUI describe intended actions, but the physical mapping remains to be validated.

Robotic-arm GUI action groups previously worked in the legacy prototype through the deployed arrangement. This is legacy operating evidence, not validation of new code. Any refactored arm-control module, transport change, action mapping, or replacement Pi requires new controlled physical validation before it may be described as working.

The retained udev rule for topology `1-2:1.0` requests `/dev/arduino_roboticarm`, but that alias is currently absent. It is not the active path and must not be used as a fallback or substituted for `/dev/ttyAMA1` without explicit investigation and physical authorization.

## Protocol-preservation requirements

Before altering any command or response:

1. Capture real, timestamped startup and command/reply transcripts with explicit authorization.
2. Add byte-for-byte fixtures and mock controller tests.
3. Define backward compatibility and controller reset behavior.
4. Separate transport timeouts from motion/action deadlines.
5. Treat acknowledgements, retries, emergency stop, and fail-safe outputs as intentional future protocol changes requiring physical fault testing.
