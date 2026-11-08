# GrowTech Wall handover

Mechanical, electrical and programming handover for the GrowTech Wall prototype, with interactive catalogues, source code, Nano firmware, the active vision model and saved robotic-arm actions and native CAD.

## Clone and start

```sh
git clone https://github.com/TanzH1225/GrowTech-Wall-Handover.git
cd GrowTech-Wall-Handover
python -B scripts/check.py
```

Use Python 3.11 with Tkinter available. On Windows/macOS, use a Python installation with Tcl/Tk support; on Debian/Ubuntu install the matching `python3-tk` OS package. The desk checks use the standard library and do not require camera, serial or machine-learning packages.

To open the laptop simulation:

```sh
python "source code/Raspberry Pi/GUI/refactored/app.py" --simulate
```

Simulation uses in-memory controllers and fake vision. Hardware mode is a separate Raspberry Pi operation; do not start it on an attached prototype merely to inspect the software.

## Read the handover

After cloning, open **[documentation/START-HERE.html](documentation/START-HERE.html)** in a browser. GitHub displays HTML as source, so use the local cloned copy for the interactive pages.

| Resource | Contents |
|---|---|
| [Mechanical catalogue](documentation/Mechanical%20catalog/Mechanical-CAD-Review.html) | Assemblies, fabrication, standard parts, materials, suppliers and previews |
| [Electrical catalogue](documentation/Electrical%20catalog/Electrical-Catalogue.html) | Installed components, interactive wire tracing, pin schedules and Rev J drawings |
| [Mechanical handover](documentation/GrowTech-Wall-Mechanical-Handover.docx) | Mechanisms, operation and servicing |
| [Electrical handover](documentation/GrowTech-Wall-Electrical-Handover.docx) | Power, pins, wiring and verification limits |
| [Electrical schematic set](documentation/GrowTech-Wall-Electrical-RevJ.pdf) | Eight original Rev J sheets |
| [Programming handover](documentation/GrowTech-Wall-Programming-Handover.docx) | Software architecture, controllers, vision and recovery |
| [Current source and startup](documentation/programming/Source-selection-and-startup.html) | Source selection, model path and startup |
| [Original project report](documentation/reference/Project%20reports/KIG3011_Sem%202_Report_G21.docx) | Original design and experiment context |

## CAD library

The complete arranged native CAD library is included in a normal clone:

- [Assembly](CAD%20library/Assembly/): full system and subassemblies; open `GTW003C.SLDASM` for the complete system.
- [FAB](CAD%20library/FAB/): fabrication models, print exports and electrical-box mounts/covers.
- [Standard](CAD%20library/Standard/): purchased and standard components.

Keep the folder structure together so assembly references and catalogue links can resolve. `GTW003C.zip` is excluded from Git; the unpacked native files are the shared CAD copy. No separate CAD download or Git LFS is required. The largest CAD file is below GitHub's 100 MiB per-file limit.

## Current source

| Component | Entry point |
|---|---|
| Pi GUI and coordinator | `source code/Raspberry Pi/GUI/refactored/app.py` |
| Gantry Nano | `source code/gantry_main_refactored/gantry_main_refactored.ino` |
| Hydroponics Nano | `source code/NFT_Hydroponics_refactored/NFT_Hydroponics_refactored.ino` |
| Vision model | `source code/Raspberry Pi/GUI/bestv5.pt` |
| Arm action files | `source code/Arm Action File/` |

The source files are copied from the latest self-contained handover. Their existing filenames are retained. The model resolves relative to the GUI directory. The Pi supervises two USB-connected Nanos and a separate Hiwonder controller on `/dev/ttyAMA1`; neither Nano commands the arm.

## Raspberry Pi and Nano deployment

The simulation and mock suite do not install the Pi runtime. [requirements-pi.txt](source%20code/requirements-pi.txt) records direct versions from the captured Pi environment. Reproduce the environment and follow the [Pi deployment evidence](documentation/programming/reference/pi-deployment-manifest.html) before hardware operation. UART configuration and USB aliases are installation-specific.

Open each Nano `.ino` from its matching project folder so Arduino IDE includes the adjacent headers and C++ files. Gantry uses **AccelStepper**; hydroponics uses **Adafruit RTClib**. Exact board/bootloader settings and library/compiler versions still need to be recorded from the working build. No firmware compilation or upload is claimed by this repository's desk checks.

The owner reported successful prototype use of the application branch and both updated Nano projects. The imported handover records the available evidence and remaining physical checks. E-stop actuator-power loss can drop the vertical gantry, and hidden relay/contact details remain untraced.

## Project history

The [original project repository](https://github.com/TanzH1225/IDP-Grow-Tech-Wall) remains unchanged, preserving its history and published file links. This repository is the current cloneable handover snapshot. Historical comparisons in the detailed documents refer to the earlier project; use the source paths listed above for this checkout.
