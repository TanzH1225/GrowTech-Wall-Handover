# Evidence and change record

## November 2026 documentation release

The entries below retain the 9 October review record. Those documents/comments were subsequently committed as `bccf0ae`; the pre-release source baseline for this handover is `f1ab759ebe517d81a11bb1b057cdfa5332a0a3fd` on `refactor/gui-architecture`. The November release adds a newcomer handbook, Word edition, programming ZIP and the [Hiwonder controller chapter](09-hiwonder-arm-controller.html).

The owner identified the installed board as the linked Hiwonder Bus Servo Controller and the PC tool as Bus Servo Control V3.4.exe, with groups already stored on the board and called by Pi serial. Official references now explain the general editing/download method and optional receive/joint-control capabilities. Exact live group-file and servo-ID mapping remains a prototype record to complete. [Report and asset context](10-reference-context-and-assets.html) records later evidence missing from the original software-only audit.

Only documentation, photographs and packaging utilities are changed in this release. No application/firmware changes, hardware operation, controller downloads, Pi configuration changes or model execution are part of it. Prior test counts remain dated prior evidence; this release checks documentation links, package contents/hashes and rendered Word layout.

## Original October review

This record makes the programming passdown reviewable. It documents the **refactored implementation**, using current legacy source for comparisons and captured deployment records only for their stated observations. Unknowns remain unknown. Mechanical design, electronics/wiring design and physical commissioning are deferred.

## Baseline and authorization

| Item | Recorded value |
|---|---|
| Handover date | 2026-10-09, user timezone Asia/Kuala_Lumpur |
| Repository | `GrowTech-Wall-Handover` |
| Branch | `refactor/gui-architecture` |
| Source baseline HEAD | `f6d8c6003382ca38fc7969202015d7ee22dfce84` |
| Initial tracked worktree | Clean; branch tracked `origin/refactor/gui-architecture` |
| Pre-existing untracked artifact | `docs/programming-handover-master-prompt.md`, created in the preceding user-requested prompt-preparation turn; retained |
| Authorized task | Execute that prompt: programming documents and explanatory comments, preserving executable behavior |
| User steering | Refactored version is the primary subject; legacy remains comparison/rollback evidence |
| Delivery state | Uncommitted working-tree documents/comments; no Git branch change, commit, push, merge or deployment |

The source commit identifies the code before this handover's comments. It does not identify what is flashed on either Nano, stored on the arm controller, or currently running on the Pi. A subsequent [owner prototype confirmation](reference/prototype-test-confirmation.html) reports successful branch operation and both updated Nano firmware versions. No detailed procedure/result record or exact tested revision was supplied; no physical test was performed by the assistant.

## Evidence vocabulary

| Label | Meaning in this package |
|---|---|
| Verified legacy behavior | Directly supported by preserved source, Git history, captured environment or an explicitly recorded legacy observation; state which kind supports the claim |
| Desk-verified future work | Refactored implementation inspected or checked with static analysis, mocks, synthetic fixtures or laptop tests |
| Operator-confirmed laptop simulation | Earlier recorded human observation in simulation; a form of desk evidence, not physical validation |
| Hardware-validated future work | Requires actual identified hardware/state, procedure, expected/observed outcome, date and operator; no new result here |
| Unverified detail / inference | Missing evidence or a conclusion not directly observed; not promoted to fact |
| Deferred improvement | A recommendation, not implemented or validated by this pass |

The package's source-derived protocol examples are not serial captures. Static gantry tests establish selected source constructs, not safety certification. Model hashes prove file identity, not accuracy. Firmware code comparisons do not establish compilation or physical equivalence.

## Important claim-to-source map

Function/class names are used instead of moving line numbers. Paths link to the inspected source at this checkout; use the baseline commit above to reproduce the pre-comment version.

| Claim | Evidence location | Boundary |
|---|---|---|
| Four independent control roles; Pi does not own Nano GPIO | [responsibility map](reference/controller-responsibility-map.html), [app factory](../../source%20code/Raspberry%20Pi/GUI/refactored/app.py), both firmware entry points | Source ownership and recorded architecture |
| Explicit mock composition and platform gate before hardware imports | `create_controller`, `verify_hardware_platform`, [import/platform tests](../../source%20code/Raspberry%20Pi/GUI/refactored/tests) | Desk source/tests; gate does not authenticate a deployment |
| Provider start order and offline reporting | [ApplicationController.start](../../source%20code/Raspberry%20Pi/GUI/refactored/services/controller.py) | Source lifecycle, not tested live startup |
| Four worker lanes and main-thread event delivery | [controller](../../source%20code/Raspberry%20Pi/GUI/refactored/services/controller.py), [worker_lane](../../source%20code/Raspberry%20Pi/GUI/refactored/services/worker_lane.py), [GrowTechWindow](../../source%20code/Raspberry%20Pi/GUI/refactored/gui/main_window.py) | Source plus mocked coordination/GUI tests |
| Requested/reported state, generations and rejected stale targets | [ApplicationState.apply/wait methods](../../source%20code/Raspberry%20Pi/GUI/refactored/services/state.py), `test_state.py`, `test_events.py` | Local freshness, not wire transaction correlation |
| Legacy per-group refresh is absent from refactor | GTW_GUIv2.refresh_gantry_position_before_arm/run_action_group_with_delay, [WorkflowService](../../source%20code/Raspberry%20Pi/GUI/refactored/services/workflows.py), Git `b87a4f4` | Current-source compatibility gap; no change made |
| Pesticide lacks refactored position gate | `ApplicationController.pesticide`, `WorkflowService.pesticide`, current legacy `handle_pesticide` | Source behavior, no new physical result |
| Text bytes/frame construction and line/status parsing | [protocols](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/protocols.py), [line parser](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/line_parser.py), [clients](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/clients.py), ServoControl | Pure builders/fake transports; no captured wire traffic |
| Nano settle/reset vs native arm open policy | [SerialTransport.open](../../source%20code/Raspberry%20Pi/GUI/refactored/comm/serial_transport.py), [settings](../../source%20code/Raspberry%20Pi/GUI/refactored/config/settings.py), `test_serial_transport.py` | Source/fake handle policy; actual bridge reset unverified |
| Existing gantry fault disable/debounce changes | [GantryMotion](../../source%20code/gantry_main_refactored/GantryMotion.cpp), legacy GantryController, Git `677d498`, [source tests](../../source%20code/Raspberry%20Pi/GUI/refactored/tests/test_gantry_firmware_safety.py) | Intentional source changes already present; not physical safety proof |
| Gantry blocking moves/timeout/`O` and measured grid arrays | [GantryCommandProcessor](../../source%20code/gantry_main_refactored/GantryCommandProcessor.cpp), [GantryConfig](../../source%20code/gantry_main_refactored/GantryConfig.cpp), motion files | Source execution and constants, not installed calibration |
| Hydro conversion/update order, dose durations and RTC override | [HydroponicsController](../../source%20code/NFT_Hydroponics_refactored/HydroponicsController.cpp), [config](../../source%20code/NFT_Hydroponics_refactored/HydroponicsConfig.h), timestamped baseline | Source comparison; physical accuracy/flow missing |
| Inference exception can still produce ordinary result/save | [HardwareVisionService.capture](../../source%20code/Raspberry%20Pi/GUI/refactored/vision/hardware.py), `test_vision.py` | Fake-model check; partial candidates may survive |
| ROI/label/picture policy | [vision logic](../../source%20code/Raspberry%20Pi/GUI/refactored/vision/logic.py), [AutomationService](../../source%20code/Raspberry%20Pi/GUI/refactored/services/automation.py), [domain models](../../source%20code/Raspberry%20Pi/GUI/refactored/domain/models.py) | Source/synthetic fixtures; class provenance unverified |
| Nine models and twelve arm assets | Files/size/hash inventory in [05](05-vision-and-assets.html) | Binary bytes read for identity only; no model or arm file loading |
| Manual legacy startup, aliases, boot/console and remote-access evidence | [AGENTS.md](reference/Repository-guidance.html), [Pi environment](reference/pi-environment.html), [deployment manifest](reference/pi-deployment-manifest.html), environment capture | Captured/supplied legacy evidence; no live recheck |

## Historical-record reconciliation

Original records are retained for traceability, with dated navigation notes added to the audit, phase status, architecture and limitations documents. Do not silently reinterpret an old phase's result as a fresh validation.

| Earlier claim or ambiguity | Current-source reconciliation | New package location |
|---|---|---|
| Parallel implementation/requirements are uncommitted or absent | Tracked files were committed by `738958f` and later changes; current branch is tracked and was clean at task start except the new master prompt. Git presence does not prove deployment | [01](01-system-and-code-map.html), [06](06-development-testing-and-recovery.html) |
| July audit's GUI size and behavior | Current legacy source contains later changes; rely on function/source evidence rather than the audit's fixed line count | [02](02-pi-application.html) |
| Refactor preserves arm command ordering/legacy behavior | Current legacy adds per-group same-coordinate command with a 45 s matching-POS wait and pesticide-before-dose gate; refactor lacks them | [02](02-pi-application.html), [03](03-communications.html), [07](07-maintenance-and-open-issues.html) |
| Scan-only 100-ms cancellation slices described as refactor-only improvement | Current legacy also slices the post-capture delay; dated phase comparison predates that source | [02](02-pi-application.html) |
| Refactored fault behavior described as legacy no-disable halt | `677d498` on 2026-07-30 changes fault disable, speed zeroing and switch-edge/debounce behavior. Legacy remains different | [04](04-controller-firmware.html) |
| Internal firmware modularization broadly deferred | Legacy gantry already includes `.ino/.h/.cpp`; both parallel firmware folders exist. Physical gates/build metadata still pending | [01](01-system-and-code-map.html), [04](04-controller-firmware.html) |
| Reset Serial resets only Nano serial endpoints | Current `reset_serial()` includes vision restart; UI says Reset Devices. Quiescence is bounded, but total provider reopening is not | [02](02-pi-application.html) |
| All model/camera failures stop operation | Startup/final read/save failures propagate, but capture catches inference/box iteration failures and may still save/use remaining candidates or `No detection` | [05](05-vision-and-assets.html) |
| Protocol parser validation implies sensor plausibility | `parse_hydro_status()` accepts convertible sensor floats including `NaN`/infinity; no physical plausibility policy | [03](03-communications.html), [07](07-maintenance-and-open-issues.html) |
| Only patrol has duplicate START | `G` also prints START before the grid helper prints another | [03](03-communications.html), [04](04-controller-firmware.html) |
| 87 tests prove current HEAD | July's 87 tests remain historical; this task freshly ran 89, including later gantry source checks | [06](06-development-testing-and-recovery.html) |

The older deployment/validation plan remains a future procedure, not an executed record. Apply these source reconciliations when preparing a later procedure; this handover does not authorize or claim any of its hardware steps.

## Changes delivered

The package contains an index and eight linked chapters. Four existing documents gain brief dated notes linking to this package; their original evidence is preserved. The master prompt from the preceding turn is retained unchanged.

Explanatory annotations cover **31 existing source files**: 17 Python and 14 C++/Arduino files. All are ordinary comments. They explain resource boundaries, state/report meanings, concurrency, protocol fields, timing assumptions and existing limitations.

| Source group | Files annotated |
|---|---|
| Legacy Pi references | `Raspberry Pi/GUI/GTW_GUIv2.py`, `ServoControl.py` |
| Refactored composition/config/domain | `app.py`, `config/settings.py`, `domain/grid.py` |
| Refactored communication | `comm/clients.py`, `line_parser.py`, `protocols.py`, `serial_transport.py` |
| Refactored coordination/GUI | `services/controller.py`, `automation.py`, `workflows.py`, `worker_lane.py`, `state.py`, `gui/main_window.py` |
| Refactored vision | `vision/logic.py`, `hardware.py` |
| Legacy firmware references | Gantry `.ino/.h/.cpp`; timestamped hydroponics `.ino` |
| Refactored gantry | All seven `.ino/.h/.cpp` files in `gantry_main_refactored/` |
| Refactored hydroponics | `HydroponicsConfig.h`, `HydroponicsController.h/.cpp`; thin `.ino` left as-is |

The complete path map is in [01](01-system-and-code-map.html). No tests, dependency files, binary assets, historical sketches, runtime behavior, protocol text, constants, model policies or deployment configuration were modified.

## Validation performed and limits

| Check | Method/result |
|---|---|
| Repository/history inspection | `git rev-parse --show-toplevel`, `git branch --show-current`, `git rev-parse HEAD`, `git status --short --branch`, focused `git log/show`, source/docs text reads |
| Existing laptop suite | Guarded standard-library discovery, Python 3.11.9, **89 passed**, 0 failures/errors/skips, 1.258 s; see [06](06-development-testing-and-recovery.html) for isolation/command detail |
| Python comments | **17 files passed** before/after AST equality with `type_comments=True`, excluding location attributes, plus non-comment token sequence comparison to baseline HEAD. No imports/execution of annotated files for this check |
| C++/Arduino comments | **14 files passed** string/character/raw-literal-aware non-comment token and preprocessor-line comparison to HEAD; escaped characters remain inside literal tokens. No regex-only comment stripping or compilation |
| Syntax and documentation | **51 tracked Python files parsed** in memory; **287 local Markdown targets** and balanced fences checked across all nine package files and the four historical records with notes; source symbols and chapter claims reviewed |
| Scope/whitespace | `git diff --check`, full annotated-source diff review and changed-file inventory; no unrelated file mutations |

Source comparisons account for Git's normalized text versus Windows checkout newline styles. Edits preserve existing working-file newline styles where possible; no newline setting or encoding declaration changed. Git's LF-to-CRLF checkout warnings are not executable-token differences.

All nine package files are present and checked; comment preservation, syntax, local links/fences and diff whitespace checks passed. No new tests were added. No new interactive GUI inspection, real inference, firmware compile, serial/camera/GPIO/I2C access, Pi configuration change or physical validation occurred. The headless suite uses fakes even when a test names a hardware-provider class.

## Remaining evidence and excluded work

Unresolved software/deployment facts include actual installed/flashed versions, Nano build metadata, captured startup/reset/command transcripts, reproducible Pi ARM dependency sources, model training/class provenance and arm controller file/slot mapping. Calibration math is known from source but its physical accuracy and the one-mL-per-second dose assumption are unverified.

Later mechanical/electronics work includes schematics/harness identity, installed polarity, travel/geometry/clearance, driver settings, sensor/flow calibration and physical stop design. Their software implications are recorded here; their design/capture/testing deliverables are not attempted.

The next programmer can start with the [onboarding checklist](07-maintenance-and-open-issues.html). The next behavior-changing phase should select one prioritized gap, capture desk fixtures and required physical acceptance criteria, and remain reversible. Completing this programming handover does not close those validation gaps.
