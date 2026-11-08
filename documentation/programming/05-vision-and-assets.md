# Vision pipeline, model files and robotic-arm assets

> November 2026 update: this is a detailed source reference. Start with the [current handbook](PROGRAMMING-HANDBOOK.html). The [owner's successful prototype report](reference/prototype-test-confirmation.html) covers the software branch and both updated Nano versions. The [Hiwonder chapter](09-hiwonder-arm-controller.html) supplies the now-confirmed controller and PC tool, official loading route and development references; the [report and asset note](10-reference-context-and-assets.html) adds subsequent report/dataset evidence. Original dates below identify the earlier review session, not a new deployment test.

Prepared 2026-10-09 from source commit `f6d8c6003382ca38fc7969202015d7ee22dfce84` on `refactor/gui-architecture`. This chapter prioritizes the structured implementation. Its pipeline is **desk-verified future work**, with source and mock evidence; no camera/model runtime or physical accuracy test was performed for this handover. Model names and arm filenames establish artifact identity, not training provenance, board deployment or physical action mapping.

Read the [package index](README.html), [Pi application](02-pi-application.html), [communications](03-communications.html) and [maintenance gaps](07-maintenance-and-open-issues.html). Preserve the [deployment manifest](reference/pi-deployment-manifest.html) and legacy `GTW_GUIv2.py` operator-startup contract until a later approved phase.

## Modules and responsibility boundaries

| Artifact/API | Caller, input and result | Side effects and failure boundary |
|---|---|---|
| [VisionConfig](../../source%20code/Raspberry%20Pi/GUI/refactored/config/settings.py) | Composed by `AppConfig`; supplies model/camera/filter/store defaults | Immutable Python configuration; no device access |
| [HardwareVisionService.start()/stop()](../../source%20code/Raspberry%20Pi/GUI/refactored/vision/hardware.py) | Explicitly invoked by application lifecycle in hardware mode | Imports OpenCV/Ultralytics, loads model, opens camera; releases camera on failure/stop |
| `HardwareVisionService.capture(plant)` | Manual capture or automation worker; plant index 1–24; returns `VisionResult` | Waits/grabs/reads camera, infers, annotates, creates directories and writes PNG; may raise `HardwareUnavailableError` |
| [roi_bounds()/select_best_detection()](../../source%20code/Raspberry%20Pi/GUI/refactored/vision/logic.py) | Hardware service and pure tests; image width, detection metadata, configured fractions/confidence | Computes bounds/selection without image/model imports or side effects |
| `image_output_path()` | Image root, plant and local `datetime` | Returns a path; validates plant range; does not create directories or files |
| [Detection/VisionResult](../../source%20code/Raspberry%20Pi/GUI/refactored/domain/models.py) | Transport-independent immutable data values | Detection boxes are full-image integer pixels; results contain plant, label, optional confidence/path |
| [MockVisionService](../../source%20code/Raspberry%20Pi/GUI/refactored/simulation/vision.py) | Explicit simulation composition | Produces deterministic labels; records captures; no model/camera import or image write |
| [GrowTechWindow._show_vision_result()](../../source%20code/Raspberry%20Pi/GUI/refactored/gui/main_window.py) | Main-thread handling of `VISION_RESULT` | Updates labels/dashboard and creates image popup; automation popup closes after 1000 ms |

The service does not own GUI widgets or controller transports. The application coordinates movement/capture ordering; manual capture requires a fresh accepted Gantry `POS`, resolves the corresponding plant and rechecks state before acquisition. Automation sends a grid command and waits for new matching position before capture. Camera work and model inference run on workers; UI rendering occurs through the event queue on the Tk main thread. See [02](02-pi-application.html) for worker lanes and the Gantry/capture I/O lock.

## Runtime defaults and acquisition

| Setting | Current default and significance |
|---|---|
| Model path | `/home/growtechwall/Desktop/IDP-Grow-Tech-Wall/Raspberry Pi/GUI/bestv5.pt` |
| Backend | Ultralytics `YOLO` loading the `.pt` file; no ONNX fallback in structured hardware service |
| Camera | OpenCV `VideoCapture(0)`; requests width 640 and height 640 |
| Capture freshness | Sleep 0.2 s; perform five `camera.grab()` calls; then `camera.read()` |
| Source confidence filter | Accept confidence at least 0.3 |
| Region of interest (ROI) | Horizontal bounds `int(width * 1/6)` to `int(width * 5/6)`, inclusive; full image height |
| Image root | `Path("~/plant_images").expanduser()` |

`start()` loads the model before opening the camera. An unopened camera or exception during model/camera setup releases a partly opened camera and raises `HardwareUnavailableError`. Camera width/height are requests: the service does not check property-set return values or establish the actual delivered resolution until it reads a frame. Defaults are source facts, not a camera capability claim.

The 0.2 s/five-grab sequence is intended to discard stale frames, but individual `grab()` return values are ignored. A failed final `read()` raises an operation error before saving. The service has no independent capture/model lock: application coordination is responsible for avoiding overlapping work/lifecycle operations. Do not add a direct GUI call to the camera service that bypasses those boundaries.

Captured legacy package evidence records Ultralytics 8.3.147, Torch 2.7.0, torchvision 0.22.0, OpenCV 4.11.0.86, NumPy 2.2.6 and Pillow 11.2.1. This describes a prior Pi environment, not a freshly reproduced runtime. The root [requirements-pi.txt](../../source%20code/requirements-pi.txt) proposes those package pins; ARM wheel sources and replacement-Pi validation remain incomplete. [Pi environment](reference/pi-environment.html) documents the captured environment and the unresolved OpenCV package-variant question. No packages were installed here.

## Preprocessing, ROI and detection selection

1. `capture()` receives a BGR image from OpenCV and converts it to RGB using `cv2.cvtColor`. Its actual shape supplies height and width.
2. It computes ROI bounds from that width and draws a blue BGR rectangle on the frame that will be saved. Conversion occurs **before** drawing, so the RGB model input does not contain that annotation.
3. It calls `model(rgb)` on the entire image. There is no source-level crop, resize, normalization or explicit model confidence argument in this path; Ultralytics owns its own preprocessing/default filtering. The explicit 0.3 filter is applied to the detections returned by the runtime, not a promise that all raw network candidates at that threshold are returned.
4. It reads `results[0].boxes`, converts confidence to float, box coordinates to integers, and class ID to an integer. Labels come from `model.names[class_id]` at runtime. The service constructs `Detection(label, confidence, x1, y1, x2, y2)` values.
5. `Detection.center_x` is integer `(x1 + x2) // 2`. `select_best_detection()` keeps detections with confidence `>= 0.3` and `left <= center_x <= right`. It does not require the entire box inside the ROI, apply a vertical bound, select by size, or use tracking across frames.
6. The highest-confidence eligible detection wins. Equal confidence preserves the first eligible detection in iteration order. A green box and text `<label> <confidence to two decimals>` are drawn for that one selected result; other candidates are not rendered or retained in `VisionResult`.

For width 600, the bounds are 100 and 500. A box centred at 100 is eligible if its confidence qualifies, even when part of that box extends outside the ROI. A 0.99 detection centred at 50 loses eligibility to a 0.80 detection centred at 300. These are synthetic examples, covered by dependency-free selection tests.

The retained legacy comments call this a “middle third,” while code uses `width // 6` and `5 * width // 6`, keeping the central **two-thirds**. The refactor makes those fractions explicit. Changing them, the centre criterion, threshold, candidate ordering, color conversion, model backend or preprocessing is an intentional vision behavior change requiring comparative evidence.

## Label interpretation and workflow decisions

[AutomationService._run()](../../source%20code/Raspberry%20Pi/GUI/refactored/services/automation.py) handles two modes. Scan Only stores/displays the result and waits an interruptible one-second gap; it performs no classification-triggered arm workflow. Full Auto uses **case-sensitive source string tests** in this order:

| Result label | Full Auto decision |
|---|---|
| Exact `No detection`, or contains `Immatured` | Run arm group 5, intended idle/camera mode |
| Contains `Matured` | Harvest, then transplant if Stop has not been requested |
| Every other string | Pesticide workflow |

These strings are software expectations, not an independently verified model class list. The source does not establish all class IDs, all disease classes, spelling aliases, dataset composition or accuracy. A new or differently capitalized model label can fall into pesticide handling. A label containing both policy substrings reaches the first branch. The class map must be captured from an approved runtime/artifact inspection with comparative tests before any replacement model or label policy is adopted.

Inference exceptions are logged inside `capture()`; source retains any candidates accumulated before the exception, saves the annotated frame and selects from that list. If none survived, the label is `No detection` and confidence is `None`. A failure before candidate accumulation therefore produces the same result label as a healthy frame with no eligible objects. It is logged, but `VisionResult` contains no explicit inference-error field. Full Auto takes the idle branch in that case. Model/camera **startup** errors and final camera-read/image-write errors instead reach the controller/automation operation-error path. Existing blanket statements that “model failures stop the operation” need this runtime/startup distinction.

## Image storage and display

After inference/annotation, the service forms:

```text
~/plant_images/<plant-number>/<YYYYmmdd_HHMMSS>.png
```

Plant numbers are 1–24; under the documented Pi user, `~` resolves to `/home/growtechwall`. The timestamp is taken from `datetime.now()` after capture/inference, with local wall-clock second precision and no timezone suffix. Two captures of the same plant in one second can choose the same path and overwrite. There is no retention policy, sequence ID, image manifest or automatic disk cleanup in this source.

The parent directory is created with `mkdir(parents=True, exist_ok=True)`. The saved PNG is the annotated **BGR frame**, not the raw image or a cropped ROI. It includes the blue ROI rectangle and, if a selected detection exists, its green box/label. `cv2.imwrite` returning false raises `HardwareUnavailableError`; directory/write exceptions also propagate to the worker error path. The legacy implementation only caught write exceptions and did not check a false return, so could announce success without a saved image.

`VisionResult` carries plant, selected class label, confidence or `None`, and the resulting path. Event routing stores the last result and queues it for the GUI. The main thread updates that plant's detection label and dashboard. It loads PNGs with `tk.PhotoImage`, retains references to prevent Tk image disposal and uses integer subsampling when needed. Its scaling differs from the legacy Pillow/LANCZOS maximum-400-pixel resize and does not always produce a 400-pixel maximum. Image display failure shows the path without undoing the saved capture/result. Automation passes `auto_close=True`; the popup closes after 1000 ms. Legacy accepted `auto_close` but did not implement that close behavior.

Simulation uses `image_path=None`, and the GUI explicitly displays that no image was written. Its default label fixture is `Matured` for plants divisible by eight, otherwise `Immatured` for plants divisible by five, otherwise `No detection`; supplied label mappings can override these. This exercises software routing and UI behavior, not real inference.

## Model inventory and provenance

The nine tracked model files below were inspected by filename, byte size and SHA-256 on 2026-10-09. Their binary contents were **not loaded or executed**. Size/hash identity does not establish labels, training quality or deployment.

| File under `Raspberry Pi/GUI/` | Bytes | Role evidenced by current source |
|---|---:|---|
| `bestv5.pt` | 6,235,690 | Selected by legacy source and refactored `VisionConfig` |
| `bestv3.pt` | 6,235,690 | Same bytes as `bestv5.pt`; no current selection |
| `best.pt` | 12,334,463 | Alternative/historical asset; selection/provenance unresolved |
| `bestv2.pt` | 6,235,690 | Alternative/historical asset |
| `bestV42.pt` | 6,225,514 | Alternative/historical asset |
| `bestv7.pt` | 6,229,354 | Alternative/historical asset |
| `best.onnx` | 12,255,568 | ONNX variant; no active refactored backend |
| `bestv2.onnx` | 12,257,499 | ONNX variant |
| `bestV42.onnx` | 12,257,515 | ONNX variant |

`bestv5.pt` and `bestv3.pt` both hash to `87C36A815EE6A0EFDDE2BCB71BEC5B6CB1B8855A4958646DF56F4AFDC8EF9F19`. All other model hashes differ. Preserve both files and all variants for traceability; filenames are not version/quality rankings.

Legacy log strings incorrectly call the active model ONNX. If Ultralytics cannot be imported, legacy code passes the same `.pt` path to `onnxruntime.InferenceSession`, despite available `.onnx` variants; if the Ultralytics load itself fails, it does not enter that import-failure fallback. Its intended ONNX preprocessing resizes to declared input height/width, normalizes floats by 255, transposes HWC to CHW with batch dimension and interprets six-value detection rows as centre/size/confidence/class. Compatibility with any tracked ONNX output format is not established. Labels in that branch become `class_<id>`, which fall into the full-auto pesticide branch under current policy. The structured service omits this defective fallback and selects the already-intended Ultralytics `.pt` backend. Introducing a usable ONNX path remains separately validated future work.

Subsequent report evidence and a tracked Roboflow export provide dataset, augmentation and historical evaluation context; see [10](10-reference-context-and-assets.html). They do not establish a reproducible training run or a verified dataset/run-to-bestv5.pt lineage. Capture that linkage, the runtime class map and comparative camera results before replacing the model.

## Arm action assets and software intentions

The twelve files under [Arm Action File](../../source%20code/Arm%20Action%20File) are tracked binary deployment assets for the external controller. No current Pi code reads `.rob` files or uploads them. The Pi sends a group number; actions must already be present on the board. The owner confirms using Hiwonder Bus Servo Control V3.4 to prepare/download them; [09](09-hiwonder-arm-controller.html) documents the official procedure.

| Asset filename | Bytes |
|---|---:|
| `Camera_5.rob` | 264 |
| `Camera1.rob` | 264 |
| `Harvest_1.rob` | 1,752 |
| `Harvest1.rob` | 2,992 |
| `Harvest2.rob` | 3,488 |
| `Pest_6.rob` | 2,496 |
| `Pest1.rob` | 2,496 |
| `Plant_4.rob` | 2,000 |
| `Plant1.rob` | 2,000 |
| `Store_2.rob` | 1,256 |
| `Transplant_3.rob` | 2,000 |
| `Transplant1.rob` | 2,248 |

All twelve SHA-256 values differ, including equal-size/name-related pairs. None were edited. The underscored suffixes suggest possible group associations, but this is **unverified naming evidence**, not a deployment mapping.

`AppConfig.arm_actions` and legacy `GROUP_DURATIONS` express these software intentions:

| Group sent | Description in source | Assumed wait |
|---|---|---:|
| 1 | Harvest pick-up | 4 s |
| 2 | Rotate/store in basket | 4 s |
| 3 | Pick new seedling from rack | 5 s |
| 4 | Plant seedling into spot | 7 s |
| 5 | Idle/camera mode | 1 s |
| 6 | Pesticide spray | 10 s |

The waits are completion assumptions because the Pi reads no arm response. The source descriptions do not prove which asset/version occupies each board slot. The controller family, owner-used PC tool/version and general manufacturer download route are now documented in [09](09-hiwonder-arm-controller.html). Actual controller revision/firmware, exact file-to-slot manifest, joint IDs and physical completion/clearance records still require capture. Saving a local action file is not proof that the board's live actions were exported.

See [03](03-communications.html) for exact run/stop frames, byte ordering and the current refactored gap in legacy Gantry refresh before arm actions. Safe desk investigation uses synthetic `Detection` values, fake OpenCV/model/camera objects, temporary output directories and [existing vision tests](../../source%20code/Raspberry%20Pi/GUI/refactored/tests/test_vision.py). Neither simulation labels nor injected fake inference constitute a real model or camera test. Verification results and limits are recorded in [08](08-evidence-and-change-record.html).
