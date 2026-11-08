# Original project report programming extracts

Source: **KIG3011 Sem 2 Report G21**, owner-supplied complete report, Semester II 2024/2025. The paragraphs and tables below are transcribed from the original Word XML in document order. Block numbers identify positions in the report body, not page numbers. Figures are listed by original caption; selected original screenshots and photos are in [the media guide](media-guide.html).

These are historical report claims. Use the [current source reconciliation](../10-reference-context-and-assets.html) for the active threshold, metrics discrepancies and dataset lineage limits. The extracts are not new validation results.

<!-- Original report block 349 -->

The gantry Arduino Nano is responsible for driving three NEMA 23 stepper motors—one for the X-axis and two for the Y-axis—using TB6600 stepper drivers. To achieve precise position control, the system employs limit switches on each axis for homing routines and safety boundaries. Meanwhile, the hydroponic Arduino Nano handles sensor acquisition (pH, EC, and water level) and actuates three peristaltic pumps and one main water circulation pump based on sensor feedback. It also manages lighting automation using a DS3231 Real-Time Clock (RTC) module, which ensures accurate time-based control of the grow light schedule and nutrient dosing cycles.

<!-- Original report block 350 -->

The system’s power architecture is anchored by a 24V 16.5A industrial-grade power supply, which provides direct power to high-current devices such as stepper drivers and pumps. Voltage buck converters are employed to step down 24V to 12V and 5V, powering logic components and microcontrollers safely. A USB-C Power Delivery module ensures a clean and stable 5V input to the Raspberry Pi, isolating it from noise that may be present on the primary power bus. To maintain thermal stability, dual cooling fans (intake and exhaust) are installed within the electronics enclosure, preventing overheating of sensitive components like drivers and converters.

<!-- Original report block 351 -->

The finalized list of hardware components used is shown below:

<!-- Original report block 352 -->

Table 3.3: Electronics Components in Main Control Box.

<!-- Original report block 353 -->

| Component | Description | Function in System |
| --- | --- | --- |
| Raspberry Pi 5 | ARM-based single-board computer. | Executes AI inference (YOLOv8), controls GUI, and coordinates with subsystem microcontrollers. |
| Arduino Nano (×2) | Compact microcontrollers. | One controls gantry motors; the other handles hydroponics and sensors. |
| TB6600 Stepper Motor Drivers | Microstepping motor drivers for NEMA 23. | Provide precise step control and motion smoothness. |
| 24V 16.5A PSU | Industrial AC to DC power supply. | Supplies 24V power to motors, pumps, and fans. |
| Buck Converters (×2) | Voltage step-down regulators. | Convert 24V to 12V and 5V for microcontrollers, sensors, and auxiliary circuits. |
| USB-C PD Module | Power delivery controller. | Regulates 5V input for Raspberry Pi via USB-C. |
| RTC Module (DS3231) | Real-time clock. | Schedules light/dosing cycles and timestamps sensor data. |
| PWM Dimmer | Analog light dimmer. | Manages LED grow light brightness levels. |
| Emergency Stop Button | Latching pushbutton switch. | Halts all actuator operation during critical events or maintenance. |
| Cooling Fans (In/Out) | DC axial fans. | Maintain air circulation inside electronics box to prevent overheating. |

<!-- Original report block 354 -->

Table 3.4: Dosing Module Component and Functions.

<!-- Original report block 355 -->

| Component | Function / Description |
| --- | --- |
| 4-Channel Relay Board | Controls 12 V peristaltic pumps for dosing fertilizer A, B, and phosphoric acid, plus main water pump. |
| pH Sensor Module | Measures the acidity level of nutrient solution; connected via analog interface. |
| EC Sensor Module | Monitors nutrient concentration using conductivity measurement; interfaced via analog ADC. |
| Water Level Module | Detects minimum water level in the nutrient tank using float-switch or analog range logic. |
| Molex Connector | Serves as a modular interface to the main control box; simplifies servicing and replacement. |

<!-- Original report block 357 -->

In addition to component functions, several engineering considerations were taken into account to enhance system robustness. The use of modular controllers allows for independent fault isolation and simplifies debugging. For example, if the gantry subsystem encounters a fault, the hydroponic dosing and sensing can continue to function independently. The inclusion of an emergency stop button enhances operator safety, enabling immediate shutdown of all high-power actuators. The PWM dimmer offers control over LED intensity, which can be manually adjusted or integrated into software-based plant growth routines.

<!-- Original report block 358 -->

The power distribution network was also designed with redundancy and protection in mind. Using multiple buck converters, power is segmented across low-voltage and high-voltage zones, preventing potential interference or overcurrent damage to sensitive modules like the Raspberry Pi. The 24V power rail supports heavy loads such as stepper motors, while the 5V/12V rails power logic controllers, sensors, and lighting subsystems. The selection of high-efficiency stepper drivers and regulated switching converters contributes to overall power efficiency and thermal reliability.

<!-- Original report block 359 -->

In conclusion, the electronics design of the GrowTech Wall leverages a distributed architecture that separates high-level processing, motion control, and hydroponic regulation across dedicated hardware modules. This not only enhances scalability and maintainability, but also ensures operational safety, energy efficiency, and real-time responsiveness, making the system suitable for autonomous precision farming in urban hydroponic applications.

<!-- Original report block 360 -->

## 3.1.4 Programming Design

<!-- Original report block 361 -->

## i) Arduino Nano

<!-- Original report block 363 -->

Figure 3.24: Arduino Nano.

<!-- Original report block 364 -->

To manage the diverse functional requirements of the GrowTech Wall, two Arduino Nano microcontrollers are employed—one dedicated to the hydroponic and auto dosing module, and the other to the XY gantry. This separation enables both subsystems to operate in parallel, ensuring real-time responsiveness. For example, while the hydroponics Nano continuously monitors pH, EC, and water levels to regulate dosing actions, the gantry Nano can simultaneously execute gantry movement without blocking or interference.

<!-- Original report block 365 -->

This division of labor also enhances system stability. Each Nano is responsible for a distinct category of tasks with different timing sensitivities—sensor acquisition versus motion control. By isolating them, the system avoids conflicts in timing loops, serial congestion, or task queuing that could otherwise cause lag or instability, particularly during automated sequences like dosing or harvesting.

<!-- Original report block 366 -->

Moreover, the use of two Nanos simplifies firmware development and debugging. With clearly defined responsibilities, each controller runs a focused, modular codebase—making the overall system easier to maintain, adapt, or upgrade without affecting unrelated components. This modular approach aligns well with the system’s iterative design methodology and supports future enhancements with minimal rework.

<!-- Original report block 367 -->

Table 3.5: Function of Arduino Nano-Hydroponics.

<!-- Original report block 368 -->

| Subsystem | Function | Details |
| --- | --- | --- |
| Sensor Data Acquisition | Reads pH Sensor Data. | Measures analog voltage from pH probe, converts it to calibrated pH scale (0–14), updates periodically. |
|  | Reads EC Sensor Data. | Uses analog voltage to calculate electrical conductivity of nutrient solution, temperature compensated. |
|  | Reads Water Level Sensor. | Detects dry tank or low-water condition via analog input, flags if below critical. |
| Actuation Control | Water Pump Control. | Drives nutrient solution circulation to NFT channels. Controlled manually or automatically with an adjustable flow rate knob. |
|  | Peristaltic Pump Dosing. | Controls 3 peristaltic pumps to dose Fertilizer A, Fertilizer B, and Phosphoric Acid into the reservoir, triggered based on EC/pH readings. |
|  | Auto-Dosing Interval Logic. | Applies 10-minute delay between doses to allow solution mixing and sensor stabilization. |
|  | Spray Activation. | Activates sprayer (e.g., neem oil or water mist) using a relay or pump triggered by command from RPi. |
| Lighting & Timing | RTC (DS3231) Clock Module. | Tracks real-world time (hh:mm). Used to schedule light ON/OFF cycles and timestamp data if needed. |
|  | Lighting Control (Relay). | Based on time from RTC, activates/deactivates grow lights automatically (e.g., 07:00–19:00). |
| Communication | Serial Data to RPi. | Sends sensor values (pH, EC, temp, humidity, water level, RTC) for dashboard/UI and logging. |
|  | Receives Commands. | Listens via serial for manual or override commands from RPi GUI. |

<!-- Original report block 369 -->

Table 3.6: Function of Arduino Nano-Gantry.

<!-- Original report block 370 -->

| Subsystem | Function | Details |
| --- | --- | --- |
| Gantry Motion | Executes Gantry Movement. | Controls stepper motors (X, Y1, Y2) with TB6600 drivers for accurate grid-based motion. |
|  | Homing Sequence. | Uses 3 limit switches (X, Y1, Y2) to calibrate zero positions before any task. |
|  | Coordinates to Step Conversion. | Parses and interprets incoming coordinates (X, Y), translates to steps using predefined conversion factors. |
|  | Timeout Monitoring. | Implements movement timeout detection – if any movement command takes longer than expected, triggers a safety halt and error log. |
| Error & Status Handling | Watchdog Timeout. | If movement hangs or unresponsive, resets gantry motors and optionally returns error via serial. |
| Communication | Receives Commands from RPi. | Gantry target (X,Y). |
|  | Sends Status Updates. | After action completion, sends confirmation, motor status, or failure flag to RPi. |

<!-- Original report block 372 -->

## ii) STM32F103RCT7 Controller Board

<!-- Original report block 374 -->

Figure 3.25: Controller Board.

<!-- Original report block 375 -->

To manage the robotic arm’s multiple degrees of freedom efficiently, the GrowTech Wall utilizes a dedicated STM32F103RCT7 Controller Board specifically designed for bus-type serial servos. The board interfaces directly with the Hiwonder LX-series servos, allowing all joints to be daisy-chained over a single communication bus. This topology significantly reduces cable clutter and simplifies both electrical routing and mechanical packaging within the constrained gantry-mounted arm assembly.

<!-- Original report block 376 -->

The controller is equipped with a high-performance STM32 microcontroller, based on the ARM Cortex-M3 core, capable of executing precise motion commands with adjustable angular speed and acceleration. This embedded processing offloads real-time servo management from the Raspberry Pi, enabling smoother actuation and improved response consistency during tasks such as transplanting, harvesting, and spraying.

<!-- Original report block 377 -->

Communication with the main control system is handled via a UART interface (TX/RX) directly connected to the Raspberry Pi. Upon receiving compact command instructions, the board autonomously coordinates the motion of all four servo joints, ensuring synchronized movement and accurate positioning of the robotic arm. This layered control approach provides both high reliability and modular independence, allowing the robotic subsystem to function responsively while keeping the main processor available for higher-level vision and system coordination tasks.

<!-- Original report block 380 -->

## iii) Raspberry Pi 5

<!-- Original report block 381 -->

The Raspberry Pi 5 acts as the central processing unit for high-level decision-making, leveraging its AI capabilities to enhance automation.

<!-- Original report block 382 -->

b)

<!-- Original report block 383 -->

Figure 3.26: Machine Learning Example for a) Smart Polygon. b) Top Square.

<!-- Original report block 384 -->

The RPi 5 processes video feeds from a webcam mounted on the gantry, utilizing the YOLOv8n model for real-time image processing[18]. Its tasks include:

<!-- Original report block 385 -->

Table 3.7: Raspberry Pi 5 Task.

<!-- Original report block 386 -->

| Subsystem | Function | Details |
| --- | --- | --- |
| Camera & Inference | USB Camera Initialization. | Configures a USB webcam (640×640 resolution) for real-time capture and object detection. |
|  | Capture & Infer. | Captures plant images, runs inference (via YOLOv8 or ONNX), and annotates detections (e.g., Matured, Immatured, Disease). |
|  | Save Inference Image. | Saves annotated image snapshots with timestamp to /plant_images/{plant_number}. |
| AI Vision | Object Detection. | Uses YOLOv8 or ONNX model to detect plant conditions and updates grid UI with detection labels. |
|  | Automated Scanning. | Scans the 24-plant grid sequentially, capturing images and processing detections. |
| Robotic Arm Control | Action Group Execution. | Sends pre-programmed action group IDs to servo controller via ServoControl.setGroupRun. |
|  | Harvest | Executes group 1 & 2 (pick-up and basket storage), repositions via gantry. |
|  | Transplant | Moves to seedling rack (position 6), executes transplant groups (3 & 4). |
|  | neem oil | Triggers neem oil spray sequence via group 6. |
| XY Gantry Control | Manual Movement | Allows directional (U/D/L/R) or direct coordinate input to control stepper-based gantry. |
|  | Automation Path | Follows a predefined serpentine sequence of plant positions for inference and robotic action. |
|  | Homing / Disable | Sends homing (0 0) or disable (O) command; listens for timeout or state feedback. |
| Hydroponic Automation | pH & EC Monitoring | Continuously receives pH and EC values from Arduino Nano over serial. |
|  | Auto Dosing | Adjusts acid and fertilizer dosing based on current pH and EC against target settings. |
|  | Manual Dosing | Opens pop-up to dose Fertilizer A+B or Acid via button (mL value set by user). |
|  | Water & Light Control | Toggles grow light and water pump states with buttons; light follows a set ON/OFF schedule. |
|  | Settings Management | Allows pop-up control for Auto Dose volume, EC/pH targets, and light schedule hours. |
| Communication & Serial | Dual Serial Channels | Communicates with arduino_gantry and arduino_hydroponic via USB serial. |
|  | Command Dispatch | Sends structured serial commands (e.g., "WATER_PUMP:ON", "TARGET_EC:1500"). |
|  | Real-Time Parsing | Parses and interprets responses like STAT,... or gantry POS/STATE/TIMEOUT. |
| GUI (Tkinter) | Multi-tab Dashboard | 4 tab layout: Dashboard, Gantry & Arm, Hydroponic, Vision. |
|  | Real-Time UI Sync | Displays system states (Online/Offline), gantry coordinates, detection labels. |
|  | Manual vs Auto Mode | Allows switching between full-auto mode and manual control via unified GUI. |

<!-- Original report block 388 -->

## iii) TKinter GUI

<!-- Original report block 389 -->

The GrowTech Wall system is operated through a custom-developed graphical user interface (GUI) built using Python’s Tkinter library. The GUI is designed to run on the Raspberry Pi 5 and acts as the central control and monitoring dashboard for the entire system, integrating real-time data visualization, automation controls, and user override functions. The interface is structured with a tabbed layout comprising four main sections: Dashboard, Gantry & Arm, Hydroponic, and Vision.

<!-- Original report block 391 -->

Figure 3.27: Dashboard Tab for GrowTech.

<!-- Original report block 392 -->

The Dashboard tab provides a quick system overview. It features real-time status indicators for the XY gantry, robotic arm, dosing module, grow light, and camera, each highlighted in green when online. The left panel displays key hydroponic sensor values—water level (in %), EC (electrical conductivity), and pH—streamed directly from the Arduino Nano. The right panel shows the latest image capture from the USB camera, used for inference or verification. Below, the interface presents the most recent AI detection result and the corresponding plant position, helping operators track plant health monitoring in progress.

<!-- Original report block 394 -->

Figure 3.28: Dashboard Tab for GrowTech Wall Robotic Arm Controller Screen.

<!-- Original report block 395 -->

The Gantry & Arm tab enables manual operation of the motion subsystem. It includes directional buttons for moving the gantry (Up, Down, Left, Right, Home, Next) and action buttons for triggering harvesting, transplanting, and neem oil application. The interface also includes Auto and Capture buttons for initiating full scan-and-act automation or on-demand inference. At the core of this tab lies a 4×6 grid representing all 24 plant positions. Each button sends precise XY coordinates to the gantry and updates its background dynamically based on motion status (idle, moving, or reached). A status bar below tracks the gantry’s raw messages and arm activity state in real time.

<!-- Original report block 397 -->

Figure 3.29: Hydroponic Tab for GrowTech.

<!-- Original report block 398 -->

The Hydroponic tab centralizes all nutrient delivery and grow environment controls. The upper section provides active/inactive indicators for each actuator: Fertilizer A, Fertilizer B, Acid pump, Water pump, and Grow Light. On the left, a sensor display shows real-time readings for water level, EC, and pH, with inline Set buttons for adjusting the target values. The right panel offers manual override buttons for dosing and toggling actuators. Below, an automation settings section allows users to configure lighting schedules, auto-dosing amounts, and nutrient targets via popup dialogs. A bottom section monitors serial communication—displaying both the last command sent and the most recent structured data received from the hydroponics controller.

<!-- Original report block 400 -->

Figure 3.30: Vision Tab for GrowTech Wall.

<!-- Original report block 401 -->

The Vision tab displays plant health diagnostics generated by the AI model. A 24-cell matrix mirrors the physical layout of the hydroponic channels, with each cell labeled by plant number and the corresponding YOLOv8 classification result. Labels such as “Matured”, “Immatured”, or “No detection” are updated in real time after each inference pass. This visualization aids quick inspection and helps validate detection results before robotic actions are executed.

<!-- Original report block 402 -->

Overall, the GUI integrates all system layers—from AI and automation to sensor feedback and manual control—into a single accessible interface optimized for touchscreen deployment. Its modular layout, live feedback, and intuitive controls enhance usability and operational reliability in the GrowTech Wall’s precision farming environment.

<!-- Original report block 563 -->

## 3.2.6 Dataset Preparation and Model Training

<!-- Original report block 564 -->

The GrowTech Wall vision system utilizes a custom-trained object detection model to identify crop maturity and common diseases for Sweet Basil, Lettuce, and Bok Choy. This enables precision harvesting, early disease detection, and informed dosing decisions through automated visual inspection.

<!-- Original report block 565 -->

## i) Dataset Annotation and Class Structure

<!-- Original report block 567 -->

Figure 3.39: Dataset Annotation Classes in Roboflow.

<!-- Original report block 568 -->

Image annotation was performed using Roboflow’s object detection interface. A total of 2,050 base images were labeled into 9 specific classes, covering crop types, maturity states, and disease symptoms:

<!-- Original report block 569 -->

Table 3.13: Total of Dataset Images used for AI Training.

<!-- Original report block 570 -->

| Class | Description | Image Count |
| --- | --- | --- |
| Immature Bok Choy | Early-stage Bok Choy | 175 |
| Matured Bok Choy | Harvest-ready Bok Choy | 314 |
| White Flies Choy | Disease annotation for pest-infested leaves | 384 |
| Immature Lettuce | Young Lettuce heads | 159 |
| Matured Lettuce | Full-grown Lettuce ready for harvest | 370 |
| Septoria Lettuce | Disease annotation for spotted leaf symptoms | 252 |
| Immature Sweet Basil | Leafy green basil in early growth | 175 |
| Matured Sweet Basil | Fully grown basil leaves | 186 |
| Anthracnose Sweet Basil | Fungal-infected leaf pattern | 79 |

<!-- Original report block 571 -->

## ii) Dataset Split

<!-- Original report block 572 -->

The dataset was automatically split by Roboflow following a 70% / 20% / 10% ratio for training, validation, and testing respectively:

<!-- Original report block 573 -->

Table 3.14: Split Ratio for AI Training.

<!-- Original report block 574 -->

| Split Type | Percentage | Image Count |
| --- | --- | --- |
| Training Set | 70% | ~7,457 images |
| Validation Set | 20% | ~2,131 images |
| Test Set | 10% | ~1,066 images |

<!-- Original report block 576 -->

## iii) Data Augmentation Strategy

<!-- Original report block 577 -->

b)

<!-- Original report block 579 -->

Figure 3.40: a) Augmentations Setting b) Maximum Version Size for AI Vision.

<!-- Original report block 580 -->

To enhance robustness and reduce overfitting, extensive image augmentation was applied. This improved the model’s ability to generalize across varied lighting and camera positions within the vertical grow wall.

<!-- Original report block 581 -->

Table 3.15: Augmentation and Parameters.

<!-- Original report block 582 -->

| Augmentation Type | Parameters |
| --- | --- |
| Blur | 2.5 pixels Gaussian blur |
| Noise | 1.25% random pixel noise |
| Exposure | ±12% brightness shift |
| Shear | 10° vertical & 10° horizontal |
| Brightness | ±24% intensity range, both directions |

<!-- Original report block 583 -->

These augmentations generated a 7× expanded dataset with over 10,654 synthetic images used in training.

<!-- Original report block 585 -->

## iv) Model Training Configuration

<!-- Original report block 586 -->

Training was performed using YOLOv8 with ONNX export for deployment readiness. The model was trained locally on:

<!-- Original report block 587 -->

Table 3.16: Hardware Specifications.

<!-- Original report block 588 -->

| Hardware | Specification |
| --- | --- |
| GPU | NVIDIA GeForce RTX 3060 (6 GB VRAM) |
| CPU | AMD Ryzen 5 5600H |
| RAM | 64 GB |

<!-- Original report block 589 -->

Training Summary:

<!-- Original report block 590 -->

Epochs: 100

<!-- Original report block 591 -->

mAP50: 98.2%

<!-- Original report block 592 -->

Precision: 98.0%

<!-- Original report block 593 -->

Recall: 98.5%

<!-- Original report block 595 -->

Figure 3.41: Graph Trend Performance for Training Summary.

<!-- Original report block 597 -->

Figure 3.42: AI Reading for Bok Choy and Sweet Basil.

<!-- Original report block 600 -->

Figure 3.43: AI Reading for Septoria Lettuce and Anthracnose Sweet Basil.

<!-- Original report block 602 -->

Figure 3.44: AI Reading for Immature Bok Choy.

<!-- Original report block 848 -->

## 3.4.5 Model Training Outcome and Performance Evaluation

<!-- Original report block 850 -->

Figure 3.54: Model Deployment on GrowTechWall.

<!-- Original report block 851 -->

After completing dataset preparation and augmentation, the YOLOv8 model was trained over 100 epochs. This section reports the performance outcomes and insights from evaluation metrics, confusion matrices, and confidence calibration.

<!-- Original report block 853 -->

Figure 3.55: Model Training Outcome and Performance Evaluation.

<!-- Original report block 854 -->

## i) Training Curve Analysis

<!-- Original report block 855 -->

Training and validation loss decreased consistently across all components, as shown in Figure 3.54:

<!-- Original report block 856 -->

Table 3.32: Component and Observation.

<!-- Original report block 857 -->

| Loss Component | Observation |
| --- | --- |
| box_loss | Steadily reduced from 0.4 to <0.1, indicating precise bounding box regression. |
| cls_loss | Dropped sharply in first 20 epochs and flattened after ~50 epochs. |
| dfl_loss | Gradual convergence, confirming stability in predicted box shape distribution. |
| Validation loss | Followed a similar downward trend with no sign of overfitting. |

<!-- Original report block 858 -->

The model maintained a high degree of generalization across the 10,654 augmented training samples, validated by smooth convergence curves.

<!-- Original report block 859 -->

## ii) Precision, Recall, and F1 Performance

<!-- Original report block 861 -->

Figure 3.56: F1 Confidence Curve.

<!-- Original report block 863 -->

Figure 3.57: Precision Confidence Curve.

<!-- Original report block 866 -->

Figure 3.58: Recall-Confidence Curve.

<!-- Original report block 867 -->

Model evaluation returned the following metrics (on the 10% test set):

<!-- Original report block 868 -->

Table 3.33: Metric and Result.

<!-- Original report block 869 -->

| Metric | Result |
| --- | --- |
| mAP@0.5 | 0.990 |
| Precision | 0.995 |
| Recall | 0.989 |
| F1 Score (avg) | 0.99 @ 0.815 threshold |

<!-- Original report block 870 -->

Figure 3.55 – 3.57 visualize precision-confidence, recall-confidence, and F1-confidence curves. The model achieves near-maximum F1 at a confidence threshold of 0.815, which was used in deployment to optimize between false positives and detection certainty.

<!-- Original report block 872 -->

## iii) Confusion Matrix Analysis

<!-- Original report block 874 -->

Figure 3.59: Confusion Matrix Data.

<!-- Original report block 876 -->

Figure 3.60: Confusion Matrix Normalized Data.

<!-- Original report block 877 -->

Table 3.34: Insight and Visual Reference Data

<!-- Original report block 878 -->

| Insight | Visual Reference |
| --- | --- |
| True positive rate >98% for all maturity classes | See Figure 3.58 (Raw) |
| Minor misclassifications in Matured Lettuce and Whiteflies class | Normalized in Figure 3.59 |
| Background and disease misclassifications <2% | Implies strong class distinction |

<!-- Original report block 879 -->

The normalized matrix confirms the model consistently distinguishes between similar crop categories such as “Matured Lettuce” and “Immature Lettuce,” which was previously a challenging classification.

<!-- Original report block 881 -->

## iv) Class-wise Performance (Precision-Recall)

<!-- Original report block 883 -->

Figure 3.61: Precision-Recall Curve.

<!-- Original report block 884 -->

Table 3.35: Class Wide Performance Data.

<!-- Original report block 885 -->

| Class | Precision | Recall | mAP@0.5 |
| --- | --- | --- | --- |
| Anthracnose Sweet Basil | 0.995 | 0.995 | 0.995 |
| Immature Bok Choy | 0.995 | 0.995 | 0.995 |
| Immature Lettuce | 0.980 | 0.980 | 0.980 |
| Immature Sweet Basil | 0.995 | 0.995 | 0.995 |
| Mature Bok Choy | 0.991 | 0.991 | 0.991 |
| Mature Lettuce | 0.993 | 0.993 | 0.993 |
| Mature Sweet Basil | 0.995 | 0.995 | 0.995 |
| Septoria Lettuce | 0.969 | 0.969 | 0.969 |
| White Flies Bok Choy | 0.995 | 0.995 | 0.995 |

<!-- Original report block 886 -->

## v) Label Distribution and Bounding Box Characteristics

<!-- Original report block 888 -->

Figure 3.62: Label Distribution Data.

<!-- Original report block 889 -->

Table 3.36: Statistics Insights.

<!-- Original report block 890 -->

| Statistic | Insight |
| --- | --- |
| Most frequent class | White Flies Bok Choy (384) and Matured Lettuce (370). |
| Least frequent class | Anthracnose Sweet Basil (79). |
| Box dimensions | Mostly center-aligned, avg width-height ratio uniform. |
| Detection skew or imbalance | Not detected visually from Figure 3.61 |

<!-- Original report block 891 -->

This confirms the dataset’s label diversity and bounding box size consistency are sufficient to support stable model learning.
