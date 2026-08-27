#!/usr/bin/env python3
"""Flip U1 to the PCB bottom and add two physical 1x8 header models."""

from __future__ import annotations

import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-esp32-bottom-headers.kicad_pcb"
HEADER_MODEL = "${KIPRJMOD}/project_libraries/3D-models/ESP32-C3_SuperMini_2x08_Header.step"
MODULE_MODEL = "${KIPRJMOD}/project_libraries/3D-models/ESP32-C3_SuperMini.step"


if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
u1 = next((fp for fp in board.GetFootprints() if fp.GetReference() == "U1"), None)
if not u1:
    raise RuntimeError("U1 was not found")

# Mirror left/right while keeping the USB end at the physical rear.  This puts
# the module on B.Cu and mirrors the pad/net mapping correctly for underside
# assembly instead of merely turning the visual model upside down.
if u1.GetLayer() == pcbnew.F_Cu:
    u1.Flip(u1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
elif u1.GetLayer() != pcbnew.B_Cu:
    raise RuntimeError("U1 is on an unexpected layer")

models = u1.Models()
models.clear()

module = pcbnew.FP_3DMODEL()
module.m_Filename = MODULE_MODEL
module.m_Offset = pcbnew.VECTOR3D(-9.0, 11.26, 2.24)
module.m_Rotation = pcbnew.VECTOR3D(0.0, 0.0, 90.0)
module.m_Scale = pcbnew.VECTOR3D(1.0, 1.0, 1.0)
models.append(module)

# Project-local combined header model: two black 2.54 mm carriers plus 16
# trimmed gold pins.  It is centred on the footprint origin.
header = pcbnew.FP_3DMODEL()
header.m_Filename = HEADER_MODEL
header.m_Offset = pcbnew.VECTOR3D(0.0, 0.0, 0.0)
header.m_Rotation = pcbnew.VECTOR3D(0.0, 0.0, 0.0)
header.m_Scale = pcbnew.VECTOR3D(1.0, 1.0, 1.0)
models.append(header)

pcbnew.SaveBoard(str(BOARD_PATH), board)

print(f"Updated {BOARD_PATH}")
print(f"Backup: {BACKUP_PATH}")
print("U1 is on B.Cu with the USB still at the physical rear")
print("Added two 1x8 black-plastic/gold-pin header models; module offset is 2.24 mm")
