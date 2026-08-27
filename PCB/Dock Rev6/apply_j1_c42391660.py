#!/usr/bin/env python3
"""Replace J1 with the exact hanxia HX-XH2.54-2PZZ / LCSC C42391660 package."""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-j1-c42391660.kicad_pcb"
FOOTPRINT_LIB = ROOT / "project_libraries" / "footprints" / "DockRev6.pretty"
FOOTPRINT_NAME = "HX-XH2.54-2PZZ_C42391660"


if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
old = next((fp for fp in board.GetFootprints() if fp.GetReference() == "J1"), None)
if old is None:
    raise RuntimeError("J1 was not found")

if old.GetFPID().GetLibItemName() == FOOTPRINT_NAME:
    replacement = old
    centre = old.GetPosition()
    angle = old.GetOrientationDegrees()
else:
    old_pads = {pad.GetNumber(): pad for pad in old.Pads()}
    if set(old_pads) != {"1", "2"}:
        raise RuntimeError(f"Unexpected J1 pad set: {sorted(old_pads)}")

    # Put the new 2.50 mm pads on the same centreline as the former 2.54 mm pads.
    # This changes each pad by only 0.02 mm and retains the connector area.
    p1 = old_pads["1"].GetPosition()
    p2 = old_pads["2"].GetPosition()
    centre = pcbnew.VECTOR2I((p1.x + p2.x) // 2, (p1.y + p2.y) // 2)
    # KiCad's positive footprint rotation is opposite to the screen-coordinate
    # direction used by VECTOR2I Y, hence the minus sign.
    angle = -math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))

    replacement = pcbnew.FootprintLoad(str(FOOTPRINT_LIB), FOOTPRINT_NAME)
    if replacement is None:
        raise RuntimeError(f"Could not load DockRev6:{FOOTPRINT_NAME}")

    replacement.SetReference("J1")
    replacement.SetValue("HX-XH2.54-2PZZ")
    replacement.SetPosition(centre)
    replacement.SetOrientation(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    replacement.SetPath(old.GetPath())
    replacement.SetSheetfile(old.GetSheetfile())
    replacement.SetSheetname(old.GetSheetname())
    replacement.SetLocked(old.IsLocked())

    for pad in replacement.Pads():
        source = old_pads.get(pad.GetNumber())
        if source is None:
            raise RuntimeError(f"Replacement has unexpected pad {pad.GetNumber()}")
        pad.SetNet(source.GetNet())

    board.Add(replacement)
    board.Remove(old)

    # Refill the user's existing copper zones around the revised holes.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

# Put J1's reference to the left of its shroud, away from D2's reference.
replacement.SetFPID(pcbnew.LIB_ID("DockRev6", FOOTPRINT_NAME))
reference_offset = pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(4.8))
replacement.Reference().SetFPRelativePosition(reference_offset)
pcbnew.SaveBoard(str(BOARD_PATH), board)

library_footprint = pcbnew.FootprintLoad(str(FOOTPRINT_LIB), FOOTPRINT_NAME)
if library_footprint is None:
    raise RuntimeError(f"Could not reload DockRev6:{FOOTPRINT_NAME}")
library_footprint.Reference().SetFPRelativePosition(reference_offset)
pcbnew.FootprintSave(str(FOOTPRINT_LIB), library_footprint)

# Keep the schematic instance and project symbol library pointed at the same
# package so Update PCB from Schematic cannot restore the obsolete socket.
text_replacements = {
    "DockRev6:JST_Compatible_Female_1x02_P2.54mm":
        "DockRev6:HX-XH2.54-2PZZ_C42391660",
    "DockRev6:JST_Compatible_1x02_P2.54mm":
        "DockRev6:HX-XH2.54-2PZZ",
    "JST_Compatible_1x02_P2.54mm": "HX-XH2.54-2PZZ",
}
for text_path in (
    ROOT / "Dock Rev6.kicad_sch",
    ROOT / "project_libraries" / "symbols" / "DockRev6.kicad_sym",
):
    text = text_path.read_text()
    for source, target in text_replacements.items():
        text = text.replace(source, target)
    text_path.write_text(text)

print(f"Updated: {BOARD_PATH}")
print(f"Backup:  {BACKUP_PATH}")
print(f"J1 centre: ({pcbnew.ToMM(centre.x):.3f}, {pcbnew.ToMM(centre.y):.3f}) mm")
print(f"J1 orientation: {angle:.1f} degrees")
for pad in replacement.Pads():
    pos = pad.GetPosition()
    print(
        f"Pad {pad.GetNumber()}: {pad.GetNetname()} at "
        f"({pcbnew.ToMM(pos.x):.3f}, {pcbnew.ToMM(pos.y):.3f}) mm"
    )
