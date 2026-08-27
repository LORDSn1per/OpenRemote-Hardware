#!/usr/bin/env python3
"""Generate the dock-shaped blank PCB from the Fusion mechanical handoff.

Dock coordinates are mapped as follows:
  KiCad X = 100 mm + dock X
  KiCad Y = 100 mm - dock Z

The board intentionally contains only its mechanical definition and four M3
mounting holes. Component placement remains an owner task.
"""

from __future__ import annotations

import math
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Dock Rev6.kicad_pcb"
MOUNTING_LIB = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty")
ORIGIN_X = 100.0
ORIGIN_Y = 100.0


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


def rounded_polygon(
    vertices: list[tuple[float, float]],
    corner_cuts: list[float],
    samples: int = 8,
) -> list[tuple[float, float]]:
    """Return a smooth, closed outline using quadratic corner blends."""
    entries: list[tuple[float, float]] = []
    exits: list[tuple[float, float]] = []
    for index, vertex in enumerate(vertices):
        previous = vertices[index - 1]
        following = vertices[(index + 1) % len(vertices)]
        to_previous = unit_toward(vertex, previous)
        to_following = unit_toward(vertex, following)
        cut = min(
            corner_cuts[index],
            math.dist(vertex, previous) * 0.35,
            math.dist(vertex, following) * 0.35,
        )
        entries.append((vertex[0] + to_previous[0] * cut, vertex[1] + to_previous[1] * cut))
        exits.append((vertex[0] + to_following[0] * cut, vertex[1] + to_following[1] * cut))

    outline: list[tuple[float, float]] = []
    for index, vertex in enumerate(vertices):
        entry = entries[index]
        exit_point = exits[index]
        for step in range(samples + 1):
            t = step / samples
            omt = 1.0 - t
            outline.append(
                (
                    omt * omt * entry[0] + 2 * omt * t * vertex[0] + t * t * exit_point[0],
                    omt * omt * entry[1] + 2 * omt * t * vertex[1] + t * t * exit_point[1],
                )
            )
    return outline


def add_segment(board: pcbnew.BOARD, start: tuple[float, float], end: tuple[float, float], layer: int, width: float = 0.1) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetLayer(layer)
    shape.SetStart(point(*start))
    shape.SetEnd(point(*end))
    shape.SetWidth(mm(width))
    board.Add(shape)


def add_circle(board: pcbnew.BOARD, center: tuple[float, float], radius: float, layer: int, width: float = 0.2) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_CIRCLE)
    shape.SetLayer(layer)
    shape.SetCenter(point(*center))
    shape.SetEnd(point(center[0] + radius, center[1]))
    shape.SetWidth(mm(width))
    board.Add(shape)


def add_text(board: pcbnew.BOARD, text: str, x: float, y: float, layer: int, size: float = 1.2) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetLayer(layer)
    item.SetPosition(point(x, y))
    item.SetTextSize(point(size, size))
    item.SetTextThickness(mm(0.2))
    board.Add(item)


def add_keepout(board: pcbnew.BOARD, center: tuple[float, float], radius: float, name: str) -> None:
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetZoneName(name)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask())
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    polygon = pcbnew.VECTOR_VECTOR2I()
    for index in range(48):
        angle = 2 * math.pi * index / 48
        polygon.append(point(center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    zone.AddPolygon(polygon)
    board.Add(zone)


board = pcbnew.NewBoard(str(OUT))
board.SetFileName(str(OUT))
board.GetDesignSettings().SetBoardThickness(mm(1.6))
title = board.GetTitleBlock()
title.SetTitle("OpenRemote Charging Dock — Mechanical PCB")
title.SetDate("25 Aug 2026")
title.SetRevision("6")
title.SetCompany("OpenRemote")
title.SetComment(0, "Fusion handoff: Charging Dock Rev6 v21; component placement by owner")
title.SetComment(1, "Dock X maps to PCB X; dock Z maps to negative PCB Y")

# Dock X/Z outline. The 45x60 main body is unchanged. Both tongues are narrowed
# to 15 mm so the PCB remains outside an 8.5 mm radius around the four existing
# lid receivers (7.5 mm receiver plus 1.0 mm clearance); this resolves the
# collision in the nominal 18/20 mm handoff widths.
dock_outline = [
    (-7.5, 26.0),
    (+7.5, 26.0),
    (+7.5, 10.0),
    (+22.5, 10.0),
    (+22.5, -50.0),
    (+7.5, -50.0),
    (+7.5, -66.0),
    (-7.5, -66.0),
    (-7.5, -50.0),
    (-22.5, -50.0),
    (-22.5, 10.0),
    (-7.5, 10.0),
]
# 3 mm outer blends and 5 mm inward tongue transitions.
corner_cuts = [3, 3, 5, 3, 3, 5, 3, 3, 5, 3, 3, 5]
outline_dock = rounded_polygon(dock_outline, corner_cuts)
outline_board = [board_point(x, z) for x, z in outline_dock]
for index, start in enumerate(outline_board):
    add_segment(board, start, outline_board[(index + 1) % len(outline_board)], pcbnew.Edge_Cuts)

# Four M3 x 5 PCB screw positions from the Fusion handoff: 37 x 52 mm pattern.
mounts = [
    ("H1", +18.5, +6.0),
    ("H2", -18.5, +6.0),
    ("H3", +18.5, -46.0),
    ("H4", -18.5, -46.0),
]
for reference, dock_x, dock_z in mounts:
    footprint = pcbnew.FootprintLoad(str(MOUNTING_LIB), "MountingHole_3.2mm_M3")
    if footprint is None:
        raise RuntimeError("Could not load KiCad M3 mounting-hole footprint")
    footprint.SetReference(reference)
    footprint.SetValue("M3x5 PCB SCREW / 3.3mm NPTH")
    footprint.Reference().SetVisible(False)
    footprint.Value().SetVisible(False)
    center = board_point(dock_x, dock_z)
    footprint.SetPosition(point(*center))
    for pad in footprint.Pads():
        pad.SetSize(point(3.3, 3.3))
        pad.SetDrillSize(point(3.3, 3.3))
    board.Add(footprint)
    add_keepout(board, center, 4.0, f"{reference} M3 copper keepout R4mm")
    add_circle(board, center, 4.0, pcbnew.Dwgs_User, 0.2)

# Existing M3x8 lid-receiver exclusions from Fusion. These are reference-only and
# deliberately remain outside the finished board edge.
lid_receivers = [
    (+16.357, +21.292),
    (-16.357, +21.292),
    (+17.002, -59.142),
    (-17.002, -59.142),
]
for dock_x, dock_z in lid_receivers:
    add_circle(board, board_point(dock_x, dock_z), 8.5, pcbnew.Dwgs_User, 0.15)

# Pogo-tail centres are only mechanical references until exact tail intersection
# and polarity are confirmed in Fusion.
for dock_x in (-5.0, +5.0):
    center = board_point(dock_x, -2.041)
    add_circle(board, center, 0.6, pcbnew.Dwgs_User, 0.15)
    add_segment(board, (center[0] - 1.2, center[1]), (center[0] + 1.2, center[1]), pcbnew.Dwgs_User, 0.15)
    add_segment(board, (center[0], center[1] - 1.2), (center[0], center[1] + 1.2), pcbnew.Dwgs_User, 0.15)

add_text(board, "REAR / USB + CONTROL", *board_point(0, 20), pcbnew.Cmts_User, 1.0)
add_text(board, "FRONT / LED", *board_point(0, -58), pcbnew.Cmts_User, 1.0)
add_text(board, "POGO REFERENCE — POLARITY TBD", *board_point(0, -6), pcbnew.Cmts_User, 0.9)
add_text(board, "4x M3x5 ONLY — 3.3mm NPTH — R4mm ALL-COPPER KEEPOUT", 100, 112, pcbnew.Cmts_User, 0.85)
add_text(board, "BLANK MECHANICAL PCB — COMPONENT PLACEMENT BY OWNER", 100, 120, pcbnew.Cmts_User, 1.0)

pcbnew.SaveBoard(str(OUT), board)

# pcbnew's blank-board writer omits a stackup even when board thickness is set.
# Without this block KiCad's STEP exporter falls back to a 1.51 mm substrate.
# The explicit mask/copper/core stack below totals exactly 1.60 mm.
saved = OUT.read_text(encoding="utf-8")
stackup = '''\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White") (material "Liquid Photo"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01) (material "Dry Film") (epsilon_r 3.3) (loss_tangent 0))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01) (material "Dry Film") (epsilon_r 3.3) (loss_tangent 0))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White") (material "Liquid Photo"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
'''
saved = saved.replace("\t(setup\n", "\t(setup\n" + stackup, 1)
OUT.write_text(saved, encoding="utf-8")

print(f"Created {OUT}")
print("Outline: 45x60 mm main body, 15 mm front/rear tongues, 92 mm overall")
print("Mounting: 4x 3.3 mm NPTH on 37x52 mm pattern with R4 mm copper keepouts")
