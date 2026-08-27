#!/usr/bin/env python3
"""Re-export the Dock Rev6 board + component STEP consumed by Fusion.

The output keeps KiCad's absolute board coordinates (no origin flag), which is
what `CAD/FusionScripts/DockRev6PCBReplace` relies on for its placement
transform.  Re-run this after any board change, then re-run that Fusion script.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
ROOT = Path(__file__).resolve().parent
BOARD = ROOT / "Dock Rev6.kicad_pcb"
OUT = ROOT / "Dock Rev6 PCB Assembly.step"

command = [
    str(KICAD_CLI), "pcb", "export", "step",
    "--output", str(OUT),
    "--subst-models",
    "--no-dnp",
    "--force",
    str(BOARD),
]
result = subprocess.run(command)
if result.returncode:
    sys.exit(result.returncode)
print(f"Wrote {OUT} ({OUT.stat().st_size / 1_000_000:.1f} MB)")
