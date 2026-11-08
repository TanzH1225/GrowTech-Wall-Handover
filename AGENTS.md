# GrowTech Wall maintenance guidance

Preserve controller protocols, Nano pin assignments, timing, measured grid arrays, model bytes/labels/ROI and reset/homing behavior. Do not operate camera, serial, GPIO, motors, pumps or arm hardware during desk work.

The current entry points are listed in README.md. Source names and layout are preserved under source code/. Use `python -B scripts/check.py` for headless verification. It blocks hardware imports and Tk window creation. Do not run app.py without --simulate for software inspection.

Changes to physical behavior require a separate prototype test record. Desk tests are not hardware validation. Read the relevant programming and electrical handovers before modifying an interface. The arm controller is commanded directly by the Pi, not by either Nano.

Keep report generators, authoring caches, credentials, virtual environments and local CAD extraction outside commits. Do not publish new archives or releases unless explicitly requested by the owner.
