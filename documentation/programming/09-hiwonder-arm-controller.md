# Hiwonder arm controller: operation, action files and future control

Updated 8 November 2026. This chapter combines the owner's identification of the installed controller, the checked-in GrowTech Wall software, and the official references below. It documents the working action-group approach and gives a development route for more responsive arm control. No controller settings, actions or executable code were changed while preparing it.

## 1. What is installed and how the project uses it

The owner confirms that the arm uses the **Hiwonder Bus Servo Controller** described in the linked manual, with **Bus Servo Control V3.4.exe** on Windows for action preparation and downloading. Several action groups are already stored on the controller. During normal GrowTech Wall operation, the Raspberry Pi 5 sends a group number over its native UART and the controller executes the stored movement sequence. Neither Nano controls the arm.

The relationship is:

```text
Windows PC: Bus Servo Control V3.4
    | USB during action preparation / controller programming
    v
Hiwonder Bus Servo Controller: stored action groups -> arm servos
    ^
    | native UART during normal machine operation
Raspberry Pi 5: GUI, vision and workflow coordination
```

The owner also confirms that the controller has a local switch: OFF turns the arm off; ON produces a visible light inside its box. The joint/gripper servo cable is a yellow/red/black daisy chain; the 360-degree base has a separate three-black-wire lead. These facts identify the existing arrangement. They do not establish individual servo IDs, connector pin functions or the voltage at every servo.

This confirmation resolves earlier documentation that called the arm board and its PC programming software unidentified. Exact board revision/firmware, the live slot-to-file inventory and joint-to-servo-ID mapping still need to be recorded at the prototype before replacing actions or building joint-level control.

## 2. Official resources to keep with the project

Use these manufacturer links; the handover does not redistribute the installer or mirror the complete manual. Links were checked on 8 November 2026.

| Resource | Use |
|---|---|
| [Hiwonder Bus Servo Controller user manual](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/1.Bus_Servo_Controller_User_Manual.html) | Board interfaces, PC interface, action editing, adjustment and operation |
| [Hiwonder secondary-development documentation](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/2.Bus_Servo_Controller_Secondary_Development.html) | Section 2.1: controller serial protocol; section 2.5: Raspberry Pi examples |
| [Hiwonder Appendix](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/Appendix.html) | Official starting point for software and examples |
| [PC software folder linked by Hiwonder](https://drive.google.com/drive/folders/1AdJ1tJUo6wTj9AeKCvme3zCCPlkXfonw) | Bus Servo Control download location |
| [Controller resource folder linked by Hiwonder](https://drive.google.com/drive/folders/1ocfsyLbK9hZSZ_zu5OQy1_6I-vVmwg9D) | Supporting development resources |

**Version provenance:** V3.4 is the owner's installed software version. The live Appendix labels its link “Bus Servo Control”; this review did not download or execute an installer and does not establish that the currently offered file is V3.4. Record the version and file hash of the installer actually used when maintaining the machine. If a linked folder moves, return to the official Appendix.

The manufacturer's examples describe a general controller. GrowTech Wall's wiring, mechanical limits, action files and Pi configuration remain project-specific. A demonstration on a loose servo is not a suitable first movement for the assembled arm.

## 3. Current Pi integration

### Connection and code ownership

The configured arm endpoint is `/dev/ttyAMA1` at **9600 baud**. The recorded project wiring identifies orange Pi TX at physical pin 27 / GPIO0 to controller RX, purple Pi RX at physical pin 28 / GPIO1 from controller TX, and grey ground at physical pin 25. These are the project's captured wiring assignments; preserve its existing UART configuration. Do not substitute the often-used physical pins 8/10 without verifying and deliberately changing the Pi configuration and wiring together. The absent `/dev/arduino_roboticarm` alias is not the current endpoint. See [Pi deployment manifest](reference/pi-deployment-manifest.html).

| Source | Responsibility |
|---|---|
| ServoControl.py | Original board-protocol helpers; opens the arm UART at import |
| [comm/protocols.py](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/protocols.py) | Pure action-run and action-stop frame builders |
| [comm/clients.py](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/clients.py) | `ArmSerialClient`, explicitly opened by the application; sends commands |
| [comm/serial_transport.py](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/serial_transport.py) | Serial lifecycle and transport |
| [config/settings.py](../../source%20code/Raspberry%20Pi/GUI/refactored/config/settings.py) | Arm endpoint and group wait durations |
| [services/workflows.py](../../source%20code/Raspberry%20Pi/GUI/refactored/services/workflows.py) | Harvest, transplant and pesticide coordination |
| [Arm Action File](../../source%20code/Arm%20Action%20File) | Twelve preserved `.rob` assets |

The current modular arm client is **write-only**. It does not read controller replies or measured joint positions. “Running Group” is generated after a successful host write; it is not a controller acknowledgement. Closing the serial connection does not establish that an already-started action has stopped.

Do not import `ServoControl.py` merely to inspect it or reuse its functions in a laptop test: its top-level `serial.Serial(...)` opens hardware. Use the pure frame encoders and fake transports for desk work.

### Action groups expected by the application

The table describes the software's command contract, taken from `AppConfig.arm_actions` and the original GUI. Waits are Pi timing assumptions, not measured completion feedback.

| Board group requested | Intended action | Pi wait | Related repository filename, not a confirmed live-slot backup |
|---|---|---:|---|
| 1 | Harvest pick-up | 4 s | `Harvest_1.rob` |
| 2 | Rotate and store in basket | 4 s | `Store_2.rob` |
| 3 | Pick a new seedling from the rack | 5 s | `Transplant_3.rob` |
| 4 | Plant the seedling into the target spot | 7 s | `Plant_4.rob` |
| 5 | Return to idle/camera pose | 1 s | `Camera_5.rob` |
| 6 | Pesticide movement | 10 s | `Pest_6.rob` |

The numbered filenames are useful candidates for comparison, not proof that those exact bytes occupy the corresponding board slots. Preserve the other files too: `Camera1.rob`, `Harvest1.rob`, `Harvest2.rob`, `Pest1.rob`, `Plant1.rob` and `Transplant1.rob`. Similar filenames and equal sizes do not imply identical contents. The Pi does not open or download `.rob` files at runtime.

The implemented workflows explain why replacing a group affects more than the arm:

- **Harvest:** group 1, a short pause, group 2, then group 5. At column 1, the gantry first moves to column 2 for storage and returns before the final idle pose.
- **Transplant:** remember the current plant position, move to the seedling rack represented by plant 6, run group 3, return to the previous position, run group 4 and then group 5.
- **Pesticide:** send `DOSE:PEST:11` to the Hydro Nano, run group 6, then group 5. Pump operation and arm motion are separate controller commands.

The current original GUI refreshes gantry position before most arm groups. `WorkflowService` does not reproduce that per-group refresh; its harvest/transplant position checks and subsequent move waits are separate. Its interruptible arm helper can also report an unavailable arm and allow the containing workflow to continue. These are existing source differences, documented in [communications](03-communications.html) and [evidence](08-evidence-and-change-record.html), not changes introduced by this handover.

### Existing transmitted frames

These frame descriptions are directly evidenced by the repository's encoders and `ServoControl.py`. Values are hexadecimal; two-byte values are low byte first. There is no newline terminator or checksum byte in these board-command builders.

| Operation | Frame / source behaviour |
|---|---|
| Run group `g`, `r` repetitions | `55 55 05 06 g r-low r-high` |
| Stop a group | `55 55 02 07` |
| Set group speed percentage, original helper | `55 55 05 0B g speed-low speed-high` |
| Move one bus servo, original helper | `55 55 08 03 01 time-low time-high id position-low position-high` |
| Move `N` bus servos, original helper | `55 55 (3*N+5) 03 N time-low time-high`, followed by `id position-low position-high` for each servo |

Example generated by the current run encoder: group 5 once is `55 55 05 06 05 01 00`. It is the idle/camera group in the project configuration, not a universally safe pose on another arm.

The original single-servo helper clamps duration to 0–30000 ms and bus position to 0–1000. Out-of-range IDs are changed to 254, which is a poor default for a new validated command API. The multi-servo helper constructs its length before clamping its count, and accepts a flat alternating ID/position list without strong structural validation. Its existence is not a ready-made robust real-time control service. The PWM-named helpers in the same file are not evidence that the installed bus servos should receive PWM-style values.

## 4. Maintaining actions with Bus Servo Control

### Preserve the working configuration first

Before editing, copy the twelve repository action files to a dated working folder. Keep the originals unchanged. Record which software build and controller are being used, photograph the current connections, and stop the GrowTech GUI so that it cannot send a group during PC operation. Have the arm and gantry in an accessible supported condition; the owner has reported immediate gantry descent on loss of actuator power.

Inspect the board's existing behaviour before deciding that a similarly named local file is the correct replacement. This handover does **not** claim that the PC software can export a complete copy of all live board actions. Saving a local action list is not evidence of reading the board's current slots. If the existing slot contents cannot be recovered, preserve the working board and avoid overwriting those slots until the replacement sequence has been independently checked.

### Official editing and download route

Hiwonder's manual describes USB PC connection with the CH341 driver, editing an action list, saving it locally, selecting a controller group number and downloading the list to that slot. For existing files, use **Open action file**; save an edited copy with **Save action file**. **Run online** and **Run action** provide execution routes; downloading writes the selected board group. Group 100 is associated with the onboard offline-run function. The manual also covers servo IDs, offsets and parameter adjustment. Follow its illustrated interface instructions for the software build in use. [Manufacturer user manual](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/1.Bus_Servo_Controller_User_Manual.html).

For this prototype, apply that route as follows:

1. Open a candidate `.rob` file in the PC editor and inspect its servo IDs, target values, row order and durations. Opening a local file and commanding motion are separate steps.
2. Compare its intended start/end pose with the project operation. Identify the joint attached to each ID; do not infer ID order from cable order or filenames.
3. Prepare a revision in a separate local file. Retain a short description of the change and its expected clearance from the wall, plant holders, basket and seedling rack.
4. Use a spare slot only after confirming it is unused. If no spare slot can be established, stop before overwriting the working slots. Never assume that a filename assigns its own download destination.
5. With the prototype attended and motion permitted, check the candidate from its intended starting pose. First validate the arm movement by itself, then the associated gantry/pump sequence. Check the return pose as carefully as the main operation.
6. Record the tested file's SHA-256, selected slot and observed duration. Replace a production slot only when the replacement and recovery route are understood.
7. Recheck the Pi workflow. A longer board action with an unchanged short Pi wait can permit the next subsystem operation too early. Changing action speed also changes timing assumptions.

Do not reset all offsets, change IDs, or run a full-range demonstration as a shortcut to checking communication. Those changes can invalidate every stored action even if serial communication itself still works.

### Minimum action record

Keep one row per installed group in a project-maintained action manifest. The following is a record format to fill during physical maintenance, not an assertion that the entries have already been captured.

| Field | Record |
|---|---|
| Controller identity | Board revision, firmware if readable, local asset label |
| PC tool | Exact application filename/version and installer hash |
| Slot | Actual controller group number |
| Source | Exact `.rob` filename and SHA-256 |
| Servo configuration | ID-to-joint table, offsets, permitted ranges and modes |
| Motion | Start pose, operation, end pose, payload and clearance observations |
| Timing | Action duration observed on the prototype; associated Pi wait |
| Validation | Date, operator, setup, expected result and observed result |
| Recovery | Previously retained file/slot record and restoration procedure |

## 5. Beyond stored groups: available controller features

Hiwonder documents **0x03** for targets sent at runtime, **0x15** for position readback, **0x0F** for controller voltage, and **0x14** for unloading servos. It documents asynchronous group messages: **0x06** start, **0x07** forced stop, **0x08** natural completion. Position requests contain a count and IDs; replies contain count and ID/low-byte/high-byte triples. Voltage replies carry a little-endian millivolt value. Group completion carries group ID and repeat count. A zero run-repeat count means continuous repetition. Speed settings are percentages and do not persist after power-off. These capabilities are described by the manufacturer; reception and behaviour on this installed board have not been captured in this handover. [Controller protocol](https://wiki.hiwonder.com/projects/Bus-Servo-Controller/en/latest/docs/2.Bus_Servo_Controller_Secondary_Development.html).

This opens two useful development paths:

| Path | Benefit for GrowTech Wall | What must be added |
|---|---|---|
| Keep stored groups and read feedback | Coordinate the next operation with a controller completion event instead of only a fixed wait | Arm receive loop, binary parser, timeouts and workflow state handling |
| Send joint targets at runtime | Interactive jogging, calculated poses or future vision-guided correction | Joint calibration, validated target encoder, command ownership and motion planning |

The first is the smaller change to the present system. The second is useful for new experiments but requires an explicit joint model and operating limits. Neither feature is currently implemented as a complete application service by merely having the old helper functions available.

### Recommended receive architecture

This is an engineering proposal for future work, not current behaviour:

1. Extend the existing arm transport with one receive owner. Do not create competing readers or let several scripts independently use the same UART.
2. Buffer bytes across reads. Locate `55 55`, validate the length, wait for a complete frame, then validate command-specific payload structure. Recover from truncated or malformed frames rather than passing partial data into workflow state.
3. Publish distinct events for command sent, controller start, natural completion, forced stop, position feedback and timeout. Keep these separate from the GUI's inferred status.
4. Match completion against the action the application currently expects. Ignore or log stale/unexpected groups. The existing group message has no application-generated transaction ID, so repeated identical requests need disciplined sequencing.
5. Prevent a late completion from a cancelled operation from releasing the wait for a new operation. A local generation counter can protect software state, but it does not add a transaction field to the physical protocol.
6. Retain bounded timeout/error paths. Missing feedback must not be interpreted as successful completion or trigger automatic repetition of a potentially hazardous movement.
7. Keep Tk updates on the GUI thread through the existing event mechanism.

Before replacing the fixed waits, capture real start/completion/stop bytes and timing on the installed board. Confirm whether every relevant group produces the expected reply and how repeated groups and interruptions behave. Controller completion is still not a measurement that the gripper successfully picked a plant or that no collision occurred.

### Recommended joint-target architecture

Add a pure encoder and a transport-injected arm service, rather than importing the hardware-opening original module. The new API should reject invalid IDs, duplicate IDs, mismatched counts, non-integer values and out-of-range targets before writing anything. A rejected command should not silently become a different servo command.

Build an explicit calibration table for each installed joint: model, ID, position at reference pose, direction, usable range, offset, maximum permitted target change, payload assumptions and collision restrictions. The existing 0–1000 encoding range is not a mechanical travel guarantee. In particular, a 360-degree base must not inherit another joint's angle conversion or operating mode without verification.

Use a single motion owner with mutually exclusive modes such as stored-group execution and interactive joint control. On a mode transition, establish what the controller is doing, invalidate stale targets and require a known starting state. Prevent the GUI automation, PC tool and experimental script from issuing overlapping moves.

For a first experiment, request a small change near a recorded safe pose on a supported mechanism. Assess measured response before implementing continuous jogging, inverse kinematics, teleoperation or vision feedback. Geometry, calibration and collision checking belong in the new application; the present group runner does not supply them.

### Timing expectations

“Real-time control” here should mean responsive runtime commands with measured latency, not a hard real-time guarantee. Under the project's serial library defaults of 8 data bits, no parity and one stop bit, a byte occupies ten bit periods. At 9600 baud, a five-servo target frame from the existing helper is 22 bytes and takes approximately **22.9 ms** to serialize in one direction. This is a calculation from the current frame shape and configuration, not a measured update rate. Replies, controller processing, servo response, Python/Linux scheduling and queueing add time.

Design the update frequency from measured end-to-end behaviour. If producers generate targets faster than the link can carry them, queued old targets can make the arm react late. A future jogging service should deliberately manage outdated unsent targets and stop/cancel precedence rather than accumulating an unlimited queue.

### Controller UART and servo bus are different interfaces

The Pi currently talks to the **controller's command interface**. The controller communicates with the servos on its downstream bus. A future developer must distinguish these layers when selecting an SDK or adapting a tutorial. Direct-to-servo examples are not automatically usable through the controller's host RX/TX connection. Keep the existing controller route unless a separate design explicitly addresses electrical interface, bus direction handling, servo-specific commands and loss of stored-group functionality.

## 6. Focused troubleshooting

| Symptom | Check in this project |
|---|---|
| No arm movement while gantry/hydro work | Local arm switch, controller power, correct UART endpoint, TX/RX/common ground and selected group; USB Nano health says nothing about the arm link |
| PC tool cannot connect | Data-capable USB cable, identified controller, correct PC device/driver and software version; ensure the Pi workflow is stopped |
| Board group runs but performs the wrong task | Actual slot selected during download and file revision; filenames alone do not establish slot contents |
| Arm movement works but coordination is early/late | Stored action duration, any speed change and `AppConfig.arm_actions` wait; present code does not consume completion replies |
| New telemetry code never receives a result | Installed controller TX to Pi RX path, one receive owner, binary framing, supported command and actual captured response |
| Group is interrupted but GUI still says running | Separate physical controller state from the write-derived display; check how stop and cancellation propagate |
| New target moves the wrong joint | ID-to-joint record and duplicates; do not diagnose by sweeping the whole range |
| Actions change after a servo replacement | ID, offsets, reference mounting, usable range and retained slot/file mapping |

The controller's local power switch, an action-group stop command and the machine E-stop have different effects. Do not describe them as equivalent. The owner-reported E-stop removes actuator power and can make the vertical gantry descend immediately; software cancellation cannot be presented as a mechanical restraint.

## 7. Validation before adopting advanced control

First use laptop fixtures: fragmented/combined binary messages, invalid lengths, unknown commands, timeout paths, stale completions, command arbitration and rejected joint targets. Verify exact bytes with a fake transport; do not open the machine UART during those tests.

Then, on the prototype with physical testing explicitly authorised, record controller identity and configuration, retain the working actions, verify one command/reply exchange, validate a small motion and interruption, and only then test the complete arm/gantry/hydro workflow. Record expected and observed results. Feedback-based completion, joint targeting and all future timing changes remain separate changes requiring that evidence.

The current handover supplies the manufacturer's entry points, the existing application contract and a concrete extension design. It does not alter the working action groups or claim that the proposed receive and joint-control services have already been installed.
