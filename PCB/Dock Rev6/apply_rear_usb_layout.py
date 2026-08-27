#!/usr/bin/env python3
"""Resize Dock Rev6 for the rear-mounted ESP32-C3 and place remaining SMDs.

This is intentionally an in-place migration of the user's populated board.  It
does not regenerate the PCB from the schematic and therefore preserves routing,
net assignments, mounting holes, keepouts, and all unrelated placements.
"""

from __future__ import annotations

import math
import shutil
from datetime import datetime
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-rear-usb-layout.kicad_pcb"
ORIGIN_X = 100.0
ORIGIN_Y = 100.0

raise SystemExit(
    "This provisional front/back layout is superseded. Run "
    "apply_mechanical_correction_v2.py instead; it preserves copper zones, "
    "restores board-only M3 holes, and uses the owner-confirmed Fusion mapping."
)


def mm(value: float) -> int:
    return int(round(value * 1_000_000))


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def board_point(dock_x: float, dock_z: float) -> tuple[float, float]:
    return ORIGIN_X + dock_x, ORIGIN_Y - dock_z


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


def densify(points: list[tuple[float, float]], spacing: float = 0.8) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        count = max(1, int(math.ceil(math.dist(start, end) / spacing)))
        for step in range(count):
            t = step / count
            result.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
    return result


def scallop_rear_receivers(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Keep 0.05 mm physical clearance from the two existing rear lid bosses."""
    radius = 7.55
    left_x, right_x, centre_z = -16.357, 16.357, 21.292
    output: list[tuple[float, float]] = []
    for x, z in points:
        dz = z - centre_z
        if abs(dz) < radius and z > 10 and abs(x) < 12:
            inward = math.sqrt(max(0.0, radius * radius - dz * dz))
            if x < 0:
                x = max(x, left_x + inward)
            elif x > 0:
                x = min(x, right_x - inward)
        output.append((x, z))
    return output


def add_segment(board: pcbnew.BOARD, start: tuple[float, float], end: tuple[float, float]) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetStart(point(*start))
    shape.SetEnd(point(*end))
    shape.SetWidth(mm(0.1))
    board.Add(shape)


def set_footprint(board: pcbnew.BOARD, reference: str, x: float, y: float, rotation: float = 0.0) -> None:
    footprint = footprints_by_ref.get(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint {reference}")
    footprint.SetPosition(point(x, y))
    footprint.SetOrientationDegrees(rotation)


if not BOARD_PATH.exists():
    raise SystemExit(f"Board not found: {BOARD_PATH}")
if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
footprints_by_ref = {item.GetReference(): item for item in board.GetFootprints()}

# Complete all footprint edits before rebuilding Edge.Cuts.  KiCad 10's SWIG
# wrappers can invalidate child iterators after many new BOARD_ITEM objects are
# appended, even though the board itself remains healthy.
set_footprint(board, "U1", 99.87, 80.89, 0.0)
u1 = footprints_by_ref["U1"]
for pad in u1.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
        pad.SetSize(point(1.6, 1.6))

placements = {
    "C1": (95.0, 73.0, 0.0),
    "C2": (99.0, 73.0, 0.0),
    "C3": (109.0, 104.8, 0.0),
    "C4": (112.6, 104.8, 0.0),
    "C5": (95.0, 82.2, 0.0),
    "R1": (98.0, 82.2, 0.0),
    "R2": (105.5, 150.5, 180.0),
    "R3": (86.0, 134.5, 0.0),
    "R4": (86.0, 137.0, 0.0),
    "Q1": (88.5, 141.0, 0.0),
    "C7": (112.0, 143.0, 0.0),
}
for reference, (x, y, rotation) in placements.items():
    set_footprint(board, reference, x, y, rotation)

title = board.GetTitleBlock()
title.SetDate("25 Aug 2026")
title.SetRevision("6 - rear USB layout")
title.SetComment(0, "Rear ESP32-C3 USB-C access; board tongue extended to dock Z=29.5 mm")
title.SetComment(1, "SMD parts grouped at owning circuits; U1 USB opening centre X=-0.43, Y=11.73 mm")

# Replace Edge.Cuts only.  The front half and 45 x 60 mm main body remain as
# designed; the rear tongue grows to 18 mm nominal width and Z=29.5 mm.  Small
# scallops clear the existing lid fasteners at X=+/-16.357, Z=21.292.
for drawing in list(board.GetDrawings()):
    if drawing.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(drawing)

dock_vertices = [
    (-9.0, 29.5), (+9.0, 29.5), (+9.0, 10.0), (+22.5, 10.0),
    (+22.5, -50.0), (+7.5, -50.0), (+7.5, -66.0), (-7.5, -66.0),
    (-7.5, -50.0), (-22.5, -50.0), (-22.5, 10.0), (-9.0, 10.0),
]
corner_cuts = [1, 1, 5, 3, 3, 5, 3, 3, 5, 3, 3, 5]
outline = scallop_rear_receivers(densify(rounded_polygon(dock_vertices, corner_cuts)))
outline_board = [board_point(x, z) for x, z in outline]
for index, start in enumerate(outline_board):
    add_segment(board, start, outline_board[(index + 1) % len(outline_board)])

pcbnew.SaveBoard(str(BOARD_PATH), board)
print(f"Updated {BOARD_PATH}")
print(f"Backup: {BACKUP_PATH}")
print("Rear tongue: 18.0 mm nominal, receiver-scalloped, dock Z +10.0 to +29.5 mm")
print("Placed: C1-C5, C7, R1-R4, Q1; preserved all unrelated user placements")
