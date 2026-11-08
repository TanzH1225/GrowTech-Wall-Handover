# Current source selection and startup

This folder contains the current modular Raspberry Pi GUI, both updated Nano projects, the active model and all twelve small arm action files. Historical prototype sketches and alternate model weights are not required by these programs and are not included in source code.

## Current paths

| Component | Included path |
|---|---|
| GUI entry point | source code/Raspberry Pi/GUI/refactored/app.py |
| Active model | source code/Raspberry Pi/GUI/bestv5.pt |
| Gantry sketch | source code/gantry_main_refactored/gantry_main_refactored.ino |
| Hydroponics sketch | source code/NFT_Hydroponics_refactored/NFT_Hydroponics_refactored.ino |
| Arm actions | source code/Arm Action File |

The GUI copy resolves bestv5.pt relative to its own location, so moving this whole folder does not require the former absolute Pi model path. Its matching configuration test checks that portable path. These are the only two Python files adapted in the copy. Model bytes, serial ports, baud rates, protocols, pins, timing constants and firmware are preserved. The original repository was not modified.

## Laptop simulation

From the handover root, enter the GUI directory and run simulation:

```powershell
Set-Location 'source code/Raspberry Pi/GUI/refactored'
python -B app.py --simulate
```

The included standard-library tests can be run from that same directory after reviewing their hardware isolation:

```powershell
python -B -m unittest discover -s tests -q
```

Simulation requires Python and Tkinter. Hardware operation requires a configured Raspberry Pi and the packages listed in source code/requirements-pi.txt. Installations and OS packages are environment dependencies, not missing project assets. On a prepared Pi the current package entry is python3 app.py from the same directory with the appropriate environment active. Hardware mode opens camera/serial devices and may reset or home controllers; this packaging task did not operate them.

## Historical references

The detailed handbook retains evidence about the older GTW_GUIv2.py startup and original controller implementations. Those historical implementations are not the selected runtime in this folder. Links to excluded historical source have been removed rather than pointing outside the handover. Use the current paths above for this portable edition. The live Pi's original startup configuration remains unchanged.

All twelve .rob files are preserved because filenames alone do not identify the exact live board-slot contents. The numbered files are candidates for groups 1–6, not a verified board backup. Use the Hiwonder guide before replacing actions.
