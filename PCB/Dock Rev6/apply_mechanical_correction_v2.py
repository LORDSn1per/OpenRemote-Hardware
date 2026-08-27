#!/usr/bin/env python3
"""Correct Dock Rev6 front/back mapping and restore board-only M3 holes.

This migration deliberately preserves schematic footprints, tracks, vias, and
the owner's copper zones.  It only changes the board outline, mechanical
reference graphics, U1's sub-millimetre centring, and the four PCB mounting-hole
footprints.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-mechanical-correction-v2.kicad_pcb"
MOUNTING_LIB = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty")
ORIGIN_X = 100.0


def mm(value: float) -> int:
    return int(round(value * 1_000_000))


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def board_point(dock_x: float, dock_z: float) -> tuple[float, float]:
    # Confirmed by the owner: the physical Fusion faces are reversed from the
    # provisional handoff.  Mirror Z about the PCB main-body centre (Z=-20).
    # Therefore physical dock Z = KiCad Y - 140 mm.
    return ORIGIN_X + dock_x, 140.0 + dock_z


def unit_toward(start: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
    dx, dy = target[0] - start[0], target[1] - start[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def rounded_polygon(vertices: list[tuple[float, float]], corner_cuts: list[float], samples: int = 12) -> list[tuple[float, float]]:
    entries: list[tuple[float, float]] = []
    exits: list[tuple[float, float]] = []
    for index, vertex in enumerate(vertices):
        previous = vertices[index - 1]
        following = vertices[(index + 1) % len(vertices)]
        to_previous = unit_toward(vertex, previous)
        to_following = unit_toward(vertex, following)
        cut = min(corner_cuts[index], math.dist(vertex, previous) * 0.35, math.dist(vertex, following) * 0.35)
        entries.append((vertex[0] + to_previous[0] * cut, vertex[1] + to_previous[1] * cut))
        exits.append((vertex[0] + to_following[0] * cut, vertex[1] + to_following[1] * cut))

    outline: list[tuple[float, float]] = []
    for index, vertex in enumerate(vertices):
        entry = entries[index]
        exit_point = exits[index]
        for step in range(samples + 1):
            t = step / samples
            omt = 1.0 - t
            outline.append((
                omt * omt * entry[0] + 2 * omt * t * vertex[0] + t * t * exit_point[0],
                omt * omt * entry[1] + 2 * omt * t * vertex[1] + t * t * exit_point[1],
            ))
    return outline


def add_segment(board: pcbnew.BOARD, start: tuple[float, float], end: tuple[float, float]) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetStart(point(*start))
    shape.SetEnd(point(*end))
    shape.SetWidth(mm(0.1))
    board.Add(shape)


def add_circle(board: pcbnew.BOARD, centre: tuple[float, float], radius: float) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_CIRCLE)
    shape.SetLayer(pcbnew.Dwgs_User)
    shape.SetCenter(point(*centre))
    shape.SetEnd(point(centre[0] + radius, centre[1]))
    shape.SetWidth(mm(0.15))
    board.Add(shape)


if not BOARD_PATH.exists():
    raise SystemExit(f"Board not found: {BOARD_PATH}")
if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
footprints = {item.GetReference(): item for item in board.GetFootprints()}
drawings = list(board.GetDrawings())
zones = list(board.Zones())

# Centre the exact 18 mm ESP32 body between the physical 15 mm-diameter rear
# lid receivers.  The resulting minimum body-to-receiver clearance is 0.50 mm.
u1 = footprints.get("U1")
if not u1:
    raise RuntimeError("U1 was not found")
u1.SetPosition(point(100.0, 80.89))

# Remove any previous mounting-hole instances before adding the corrected,
# board-only copies later.
for reference in ("H1", "H2", "H3", "H4"):
    existing = footprints.get(reference)
    if existing:
        board.Remove(existing)

# Rebuild only Edge.Cuts: straight 18 mm rear tongue.  With the corrected
# receiver centres, the edge clears each physical receiver by 0.50 mm and no
# artificial scallop is required.
for drawing in drawings:
    if drawing.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(drawing)

# Remove the four obsolete R8.5 provisional receiver circles before adding any
# new drawing objects.  This ordering avoids a KiCad 10 SWIG iterator defect.
for drawing in drawings:
    if drawing.GetLayer() != pcbnew.Dwgs_User or drawing.GetShape() != pcbnew.SHAPE_T_CIRCLE:
        continue
    box = drawing.GetBoundingBox()
    if box.GetWidth() > mm(14.0) and box.GetHeight() > mm(14.0):
        board.Remove(drawing)

dock_vertices = [
    (-9.0, -69.5), (+9.0, -69.5), (+9.0, -50.0), (+22.5, -50.0),
    (+22.5, +10.0), (+7.5, +10.0), (+7.5, +26.0), (-7.5, +26.0),
    (-7.5, +10.0), (-22.5, +10.0), (-22.5, -50.0), (-9.0, -50.0),
]
corner_cuts = [1, 1, 5, 3, 3, 5, 3, 3, 5, 3, 3, 5]
outline_board = [board_point(x, z) for x, z in rounded_polygon(dock_vertices, corner_cuts)]
for index, start in enumerate(outline_board):
    add_segment(board, start, outline_board[(index + 1) % len(outline_board)])

# Exact physical receiver outlines (OD 15 mm), mirrored into the confirmed PCB
# coordinate system.  These are documentation graphics, not PCB holes.
lid_receivers = [
    (+17.002, -59.142), (-17.002, -59.142),
    (+16.357, +21.292), (-16.357, +21.292),
]
for dock_x, dock_z in lid_receivers:
    add_circle(board, board_point(dock_x, dock_z), 7.5)

# Mounting holes are board-only so Update PCB from Schematic cannot remove them.
mounts = [
    ("H1", +18.5, -46.0),
    ("H2", -18.5, -46.0),
    ("H3", +18.5, +6.0),
    ("H4", -18.5, +6.0),
]
for reference, dock_x, dock_z in mounts:
    footprint = pcbnew.FootprintLoad(str(MOUNTING_LIB), "MountingHole_3.2mm_M3")
    if footprint is None:
        raise RuntimeError("Could not load KiCad M3 mounting-hole footprint")
    footprint.SetReference(reference)
    footprint.SetValue("M3x5 PCB SCREW / 3.3mm NPTH")
    footprint.SetPosition(point(*board_point(dock_x, dock_z)))
    footprint.SetAttributes(
        footprint.GetAttributes()
        | pcbnew.FP_BOARD_ONLY
        | pcbnew.FP_EXCLUDE_FROM_BOM
        | pcbnew.FP_EXCLUDE_FROM_POS_FILES
    )
    footprint.SetLocked(True)
    footprint.Reference().SetVisible(True)
    footprint.Value().SetVisible(False)
    for pad in footprint.Pads():
        pad.SetSize(point(3.3, 3.3))
        pad.SetDrillSize(point(3.3, 3.3))
    board.Add(footprint)

title = board.GetTitleBlock()
title.SetDate("25 Aug 2026")
title.SetRevision("6 - mechanical correction v2")
title.SetComment(0, "Confirmed physical mapping: dock Z = KiCad Y - 140 mm; rear is Fusion Z=-70")
title.SetComment(1, "4x locked board-only M3 NPTH; physical receiver OD15 references; U1 centred")

# Refill the owner's zones against the corrected outline and restored holes.
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(zones)
pcbnew.SaveBoard(str(BOARD_PATH), board)

print(f"Updated {BOARD_PATH}")
print(f"Backup: {BACKUP_PATH}")
print("Restored 4 locked board-only 3.3 mm NPTH M3 holes")
print("Receiver references corrected to physical OD15 and mirrored Fusion positions")
print("Preserved and refilled all existing copper zones")
