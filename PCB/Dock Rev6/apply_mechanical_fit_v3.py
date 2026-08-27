#!/usr/bin/env python3
"""Finish the Dock Rev6 rear-wall fit without disturbing electrical work."""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-mechanical-fit-v3.kicad_pcb"
ORIGIN_X = 100.0


def mm(value: float) -> int:
    return int(round(value * 1_000_000))


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def board_point(dock_x: float, dock_z: float) -> tuple[float, float]:
    return ORIGIN_X + dock_x, 140.0 + dock_z


def unit_toward(start: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
    dx, dy = target[0] - start[0], target[1] - start[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def rounded_polygon(vertices: list[tuple[float, float]], cuts: list[float], samples: int = 12):
    entries, exits = [], []
    for index, vertex in enumerate(vertices):
        previous = vertices[index - 1]
        following = vertices[(index + 1) % len(vertices)]
        a = unit_toward(vertex, previous)
        b = unit_toward(vertex, following)
        cut = min(cuts[index], math.dist(vertex, previous) * 0.35, math.dist(vertex, following) * 0.35)
        entries.append((vertex[0] + a[0] * cut, vertex[1] + a[1] * cut))
        exits.append((vertex[0] + b[0] * cut, vertex[1] + b[1] * cut))
    result = []
    for index, vertex in enumerate(vertices):
        entry, exit_point = entries[index], exits[index]
        for step in range(samples + 1):
            t = step / samples
            omt = 1.0 - t
            result.append((
                omt * omt * entry[0] + 2 * omt * t * vertex[0] + t * t * exit_point[0],
                omt * omt * entry[1] + 2 * omt * t * vertex[1] + t * t * exit_point[1],
            ))
    return result


def add_segment(board, start, end):
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetStart(point(*start))
    shape.SetEnd(point(*end))
    shape.SetWidth(mm(0.1))
    board.Add(shape)


if not BOARD_PATH.exists():
    raise SystemExit(f"Board not found: {BOARD_PATH}")
if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
footprints = {item.GetReference(): item for item in board.GetFootprints()}
u1 = footprints.get("U1")
if not u1:
    raise RuntimeError("U1 was not found")

# Move the module 1.5 mm into the cavity.  Its USB shell still reaches 0.27 mm
# beyond the dock's Z=-70 outer face, while its PCB clears the retained skin.
u1.SetPosition(point(100.0, 82.39))

# Keep the two local button-filter parts clear of the shifted module courtyard.
# Their nets and orientation are unchanged.
for reference, x, y in (("C5", 88.0, 94.0), ("R1", 88.0, 95.5)):
    footprint = footprints.get(reference)
    if footprint:
        footprint.SetPosition(point(x, y))

for drawing in list(board.GetDrawings()):
    if drawing.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(drawing)

# Shorten only the rear tongue by 1.5 mm.  The exact 15 mm receiver references,
# four board-only M3 holes, components, nets, and copper zones remain untouched.
dock_vertices = [
    (-9.0, -68.0), (+9.0, -68.0), (+9.0, -50.0), (+22.5, -50.0),
    (+22.5, +10.0), (+7.5, +10.0), (+7.5, +26.0), (-7.5, +26.0),
    (-7.5, +10.0), (-22.5, +10.0), (-22.5, -50.0), (-9.0, -50.0),
]
corner_cuts = [1, 1, 5, 3, 3, 5, 3, 3, 5, 3, 3, 5]
outline = [board_point(x, z) for x, z in rounded_polygon(dock_vertices, corner_cuts)]
for index, start in enumerate(outline):
    add_segment(board, start, outline[(index + 1) % len(outline)])

pcbnew.SaveBoard(str(BOARD_PATH), board)

print(f"Updated {BOARD_PATH}")
print(f"Backup: {BACKUP_PATH}")
print("U1 moved to (100.00, 82.39) mm; rear tongue shortened to dock Z=-68.0 mm")
print("C5/R1 shifted left to clear the final U1 courtyard")
print("Copper zones intentionally left for KiCad's native refill after the outline edit")
