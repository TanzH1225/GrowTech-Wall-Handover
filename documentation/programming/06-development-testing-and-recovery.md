# Development, testing, and recovery

> November 2026 update: this is a detailed source reference. Start with the [current handbook](PROGRAMMING-HANDBOOK.html). The [owner's successful prototype report](reference/prototype-test-confirmation.html) covers the software branch and both updated Nano versions. The [Hiwonder chapter](09-hiwonder-arm-controller.html) supplies the now-confirmed controller and PC tool, official loading route and development references; the [report and asset note](10-reference-context-and-assets.html) adds subsequent report/dataset evidence. Original dates below identify the earlier review session, not a new deployment test.

This chapter describes the structured implementation's **laptop workflow** and the limits of its evidence. It is not permission to start hardware mode or upload firmware. Read [AGENTS.md](reference/Repository-guidance.html), [the source map](01-system-and-code-map.html), and [open issues](07-maintenance-and-open-issues.html) first.

## Development environment

The headless suite uses Python's standard library, principally `unittest`, `threading`, `queue`, `dataclasses`, and mock injection. [requirements-dev.txt](../../source%20code/requirements-dev.txt) is deliberately dependency-free. GUI construction additionally needs Tkinter; importing the GUI for fake-widget tests does not construct a Tk window. Refactored image display uses `tk.PhotoImage` and subsampling. Pillow belongs to the legacy display/captured package baseline, not this refactored display path.

The recorded Windows environment exists at `..\growtechwall-venv`; this task confirmed its interpreter runs Python **3.11.9**. That is a local development environment, not a portable dependency path or proof of the current Pi installation. The historical Pi capture records Python 3.11.2 on Debian 12/aarch64; see [Pi environment](reference/pi-environment.html).

[requirements-pi.txt](../../source%20code/requirements-pi.txt) pins NumPy 2.2.6, Pillow 11.2.1, pyserial 3.5, OpenCV 4.11.0.86, Torch 2.7.0, torchvision 0.22.0 and Ultralytics 8.3.147. These are proposed direct dependencies derived from the capture. ARM wheel sources, resolved transitive versions and an independently reproduced installation are still missing. Do not install this file into the laptop test environment just to run mocks.

The refactored entry point accepts `--simulate` and `--verbose`; it does not expose configuration-file/port/model CLI overrides. Defaults live in [config/settings.py](../../source%20code/Raspberry%20Pi/GUI/refactored/config/settings.py). Hardware composition checks Linux, aarch64 and Raspberry Pi device-tree text before hardware provider imports. That guard establishes a platform category, not the identity or readiness of the deployed system.

## Safe headless command

From PowerShell, using the already-existing local interpreter:

```powershell
Set-Location '.\source code\Raspberry Pi\GUI\refactored'
& 'python' -B -m unittest discover -s tests -q
```

For another checkout/interpreter, use its corresponding path and the same working directory. `-B` suppresses bytecode writes. This is the repository's actual runner; the generic pytest example in root guidance is conditional and does not describe this standard-library suite.

Before running a later revision, inspect added/modified tests and provider construction. Do not import the legacy GUI or arm library. Source-level inspection can use `ast.parse()` or `compile(source, filename, 'exec')` without executing the code. A successful parse is syntax evidence, not runtime or physical evidence.

## Test isolation and coverage

The suite reviewed for this handover contains 16 test modules. Hardware-capable classes are tested only through explicit fakes or injected objects:

| Test module(s) under [tests](../../source%20code/Raspberry%20Pi/GUI/refactored/tests) | Evidence provided | Isolation/limit |
|---|---|---|
| `test_import_safety.py`, `test_app_platform.py` | Import/composition isolation, platform rejection and `finally` shutdown | Child process blocks hardware/Tk imports; false-mode factory test patches platform check to reject before construction |
| `test_config.py`, `test_protocols.py` | Defaults, command validation/bytes and record parsing | Pure values/encoders; no transport |
| `test_line_parser.py` | Fragmented/combined records, bad UTF-8, oversized incomplete record | Synthetic bytes only |
| `test_serial_transport.py` | Nano vs arm buffer policy, failed-open cleanup | `sys.modules['serial']` replaced by fake Serial implementations before `open()` |
| `test_clients.py` | Reader/start/write error routing and cleanup | Client transport replaced before I/O methods |
| `test_state.py`, `test_events.py` | Freshness, matching targets, invalidation, router ordering, snapshots | Synthetic events and fake/simulated providers |
| `test_controller.py` | Queue ordering, barriers, reset/shutdown, admission, endpoint handling, capture/move ordering | In-memory `Endpoint` and deliberate blocking/failure doubles; simulation composition |
| `test_automation.py`, `test_workflow_failures.py` | Snake sequence, branching, cancellation and endpoint failure policy | Mock controllers/vision and injected sleep behavior |
| `test_simulation.py` | Mock state/reset and timed indicator lifecycles | In-memory providers and manually controlled timer scheduler |
| `test_gui_compatibility.py` | Modes/popups routing, indicators, selected styles, locks and dialogs | `GrowTechWindow.__new__`, fake widgets/variables/root and patched dialogs; no real Tk root |
| `test_vision.py` | ROI/path policy, failure image saving and startup cleanup | Synthetic detections, fake camera/model/OpenCV and temporary directories |
| `test_gantry_firmware_safety.py` | Presence/order of selected gantry fault and debounce source constructs | Reads C++ text; not compilation, pulse measurement or physical safety certification |

On **2026-10-09**, the existing suite ran successfully: **89 tests, 0 failures, 0 errors, 0 skips**, Python 3.11.9, 1.258 s as reported by the runner. The task used `python -B -` with a `unittest.defaultTestLoader.discover('tests')` wrapper and an import finder that rejects real `serial`, `cv2`, `ultralytics`, GPIO/I2C and legacy module imports; test-injected fake modules bypass discovery as intended. It also replaced `tkinter.Tk` with a failing guard. The child import-safety test installs its own explicit deny list. This establishes headless mock execution, not application display/physical equivalence.

The older 87-test and 22-focused-test records describe July checks. The current total includes later gantry source tests. They are separate dated evidence; do not replace historical results with today's number or claim this task repeated the prior operator GUI inspection.

## Optional laptop GUI inspection

After confirming Tk availability and simulation isolation, this is the software-only entry point:

```powershell
Set-Location '.\source code\Raspberry Pi\GUI\refactored'
& 'python' -B app.py --simulate
```

The command syntax/provider selection was inspected in this task; a new interactive GUI session was **not** run. The [July record](reference/refactoring-status.html) includes operator-confirmed Windows simulation. Future inspection should record the commit/date/operator and expected/observed controls instead of relying on that older observation for changed widgets.

Mocks preserve selected command/event shapes, not real timing. Gantry movement is immediate; no switches or travel are sampled. Arm groups are recorded and workflow waits collapse in simulation. Mock vision supplies deterministic labels and no image path. Mock hydroponics uses fixed sensor values and dose-display timers, without actual ADC/RTC/acidity/EC control. These differences are intentional test accommodations, not replacement controller algorithms.

## Extending the implementation

1. Select one boundary and identify the evidence level it requires.
2. Inspect source and capture synthetic/captured fixtures before changing behavior. Never fabricate a captured transcript from an encoder example.
3. Keep pure conversion in domain/protocol/vision logic; keep resource opening behind explicit providers; pass events rather than widgets to workers.
4. Use injected clocks/schedulers/transports for timing and failure cases. Include a meaningful acceptance condition, not merely a test duplicating the implementation.
5. Run the relevant existing tests. Run the suite when shared lifecycle/state/protocol behavior changes, after rechecking isolation.
6. Review protocol bytes, constants, pins, timing, model policy, reset behavior and startup path explicitly. Record intentional differences.
7. Keep deployment and physical approval separate. No merge into `main` before the phase's required physical checks pass.

For comments alone, token/AST preservation is the main check. This pass adds no tests and makes no behavior fixes. See [08](08-evidence-and-change-record.html) for the comment comparison method.

## Pi recovery and rollback references

The confirmed legacy operator procedure is **manual startup after boot**. Console `tty1` auto-login is not GUI autostart. The following is reference-only here: executing it opens hardware and may reset/home controllers.

```bash
cd "/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI"
source /home/growtechwall/venv-ultralytics/bin/activate
python3 GTW_GUIv2.py
```

Use [the deployment manifest](reference/pi-deployment-manifest.html) for SD/boot/udev/UART/service evidence and [replacement-Pi recovery](reference/new-pi-recovery.html) for recovery requirements. The active aliases in captured evidence are `/dev/arduino_gantry` → `/dev/ttyUSB1` and `/dev/arduino_hydroponic` → `/dev/ttyUSB0`; the arm uses `/dev/ttyAMA1`. They must be reverified on a replacement machine. Do not redirect the arm to the absent `/dev/arduino_roboticarm` alias.

The refactored `app.py` without `--simulate` is hardware mode. This handover does not promote it to the legacy entry point or authorize launching it. Source rollback references are `gantry_main/` with all matching modules, the timestamped hydroponics sketch, and the legacy Pi files/environment/model. A current repository file is not automatically the binary flashed on a board: capture artifact identity before a future update.

The earlier handover comments/documents were committed as `bccf0ae`. This November documentation release does not deploy software. For later rollback, identify the specific source commit and preserve unrelated work; reverting documents does not restore equipment state. Use [the future deployment plan](reference/refactored-deployment-and-validation-plan.html) for controller/software rollback after a separately authorized deployment.

Outstanding reproducibility evidence includes Nano FQBN/processor/bootloader/compiler/library versions, flashed hashes, exact Pi boot/UART/display settings, ARM wheel sources, model training/class provenance and installed arm mapping. Private SD images and authentication material remain outside Git. Mechanical/electronics capture is a later phase.
