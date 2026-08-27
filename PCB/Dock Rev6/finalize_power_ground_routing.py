#!/usr/bin/env python3
"""Finish Dock Rev6 ground connectivity and size power/LED current paths."""

from __future__ import annotations

import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-power-ground-finalize.kicad_pcb"
routing_items = []


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def close(a: pcbnew.VECTOR2I, b: pcbnew.VECTOR2I, tolerance_mm: float = 0.01) -> bool:
    tolerance = pcbnew.FromMM(tolerance_mm)
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance


def find_net(board: pcbnew.BOARD, name: str):
    net = board.FindNet(name)
    if net is None:
        raise RuntimeError(f"Net not found: {name}")
    return net


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
) -> None:
    start_point = point(*start)
    end_point = point(*end)
    for item in routing_items:
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != net_name:
            continue
        same_direction = close(item.GetStart(), start_point) and close(item.GetEnd(), end_point)
        reverse_direction = close(item.GetStart(), end_point) and close(item.GetEnd(), start_point)
        if same_direction or reverse_direction:
            item.SetWidth(pcbnew.FromMM(width_mm))
            return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start_point)
    track.SetEnd(end_point)
    track.SetLayer(layer)
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetNet(find_net(board, net_name))
    board.Add(track)
    routing_items.append(track)


def remove_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    start_point = point(*start)
    end_point = point(*end)
    for item in list(routing_items):
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != net_name:
            continue
        same_direction = close(item.GetStart(), start_point) and close(item.GetEnd(), end_point)
        reverse_direction = close(item.GetStart(), end_point) and close(item.GetEnd(), start_point)
        if same_direction or reverse_direction:
            routing_items.remove(item)
            board.Remove(item)
            return


def modify_track(
    net_name: str,
    old_start: tuple[float, float],
    old_end: tuple[float, float],
    new_layer: int,
    new_start: tuple[float, float],
    new_end: tuple[float, float],
    width_mm: float,
) -> None:
    old_start_point = point(*old_start)
    old_end_point = point(*old_end)
    for item in routing_items:
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != net_name:
            continue
        same_direction = close(item.GetStart(), old_start_point) and close(item.GetEnd(), old_end_point)
        reverse_direction = close(item.GetStart(), old_end_point) and close(item.GetEnd(), old_start_point)
        if same_direction or reverse_direction:
            item.SetStart(point(*new_start))
            item.SetEnd(point(*new_end))
            item.SetLayer(new_layer)
            item.SetWidth(pcbnew.FromMM(width_mm))
            return
    raise RuntimeError(f"Track to modify was not found: {net_name} {old_start} -> {old_end}")


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    position: tuple[float, float],
    diameter_mm: float = 0.6,
    drill_mm: float = 0.3,
) -> None:
    target = point(*position)
    for item in routing_items:
        if item.Type() == pcbnew.PCB_VIA_T and close(item.GetPosition(), target):
            if item.GetNetname() != net_name:
                raise RuntimeError(f"Existing via at {position} belongs to {item.GetNetname()}")
            return
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(target)
    via.SetWidth(pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(drill_mm))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(find_net(board, net_name))
    board.Add(via)
    routing_items.append(via)


if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
routing_items = list(board.GetTracks())

# The original 3V3 bottom trace stopped underneath C3/C4 without a plated
# connection to their front-side SMD pads. Terminate that branch at one via,
# then fan out on F.Cu to both capacitor pads.
modify_track("+3V3", (107.1, 101.1), (110.5, 104.5), pcbnew.B_Cu, (107.1, 101.1), (109.0, 103.0), 0.4)
modify_track("+3V3", (110.5, 104.5), (110.5, 107.0), pcbnew.F_Cu, (109.0, 103.0), (109.0, 104.8), 0.4)
add_via(board, "+3V3", (109.0, 103.0))
add_track(board, "+3V3", pcbnew.F_Cu, (109.0, 104.8), (110.65, 104.8), 0.4)
add_track(board, "+3V3", pcbnew.F_Cu, (109.0, 104.8), (109.0, 107.0), 0.4)
add_track(board, "+3V3", pcbnew.F_Cu, (109.0, 107.0), (110.725, 107.0), 0.4)

# Each FS8205A source pad gets a short, wide connection to the continuous
# bottom plane. The tented vias sit beneath Q1's body, clear of the gate and
# drain pins, and stitch the isolated local F.Cu GND islands.
add_via(board, "GND", (87.05, 139.5))
add_via(board, "GND", (87.05, 141.4))
add_track(board, "GND", pcbnew.F_Cu, (86.225, 139.5), (87.05, 139.5), 0.30)
add_track(board, "GND", pcbnew.F_Cu, (86.225, 141.4), (87.05, 141.4), 0.30)

# Stitch the broad front and back pours together in each major board region.
# These positions are inside GND fill on both layers and clear of component
# pads and routed signals.
for stitching_position in (
    (97.0, 88.5),
    (102.5, 89.5),
    (114.5, 97.5),
    (112.5, 120.0),
    (91.5, 131.5),
    (108.5, 141.0),
    (98.0, 119.0),
    (98.0, 144.0),
    (92.0, 151.0),
):
    add_via(board, "GND", stitching_position)

# Existing routing was uniformly 0.20 mm. Size current paths conservatively
# for standard 1 oz external copper and this dock's sub-amp loads.
widths_mm = {
    "+5V": 0.30,
    "+3V3": 0.20,
    "IR_K": 0.30,
    "IR_GATE": 0.20,
    "IR_PWM": 0.20,
    "Net-(D1-A)": 0.25,
    "Net-(D2-A)": 0.25,
    "Net-(D3-A)": 0.25,
    "Net-(D4-A)": 0.25,
    "Net-(D5-A)": 0.20,
    "Net-(U1-GPIO1{slash}A1)": 0.20,
}
for item in routing_items:
    if item.Type() == pcbnew.PCB_TRACE_T and item.GetNetname() in widths_mm:
        item.SetWidth(pcbnew.FromMM(widths_mm[item.GetNetname()]))

# A handful of short neck-downs are required where the routed centerline sits
# close to an adjacent pad, via, or the board edge.  The remaining 5 V and IR
# trunks stay at 0.30 mm; only these constrained pieces return to 0.20 mm.
for net_name, start, end in (
    ("+5V", (104.9443, 76.1760), (104.9443, 86.2827)),
    ("+5V", (108.0756, 87.3000), (105.9615, 87.3000)),
    ("+5V", (111.0500, 90.2744), (108.0756, 87.3000)),
    ("IR_K", (114.0000, 109.7750), (114.0000, 127.4987)),
    ("IR_K", (114.0000, 127.4987), (113.1213, 126.6200)),
    ("IR_K", (113.1213, 126.6200), (105.8800, 126.6200)),
    ("IR_K", (114.0000, 127.4987), (114.0000, 136.5000)),
    ("IR_K", (89.0000, 109.9750), (89.0000, 124.4987)),
    ("IR_K", (89.0000, 124.4987), (81.0000, 132.4987)),
):
    add_track(board, net_name, pcbnew.F_Cu, start, end, 0.20)

# Clear the remaining non-electrical DRC warnings.  These references were
# sitting on component graphics or outside the board outline, so leave their
# values in the design but do not print them on silkscreen.  U1 intentionally
# overhangs the rear edge for USB access; omit only the two vertical outline
# strokes that cross Edge.Cuts.
for hidden_reference in ("U2", "D3", "H1", "H2", "H3", "H4"):
    footprint = board.FindFootprintByReference(hidden_reference)
    if footprint is not None:
        footprint.Reference().SetVisible(False)

u1 = board.FindFootprintByReference("U1")
if u1 is not None:
    for graphic in list(u1.GraphicalItems()):
        if graphic.GetLayer() != pcbnew.B_SilkS or not hasattr(graphic, "GetStart"):
            continue
        start = graphic.GetStart()
        end = graphic.GetEnd()
        is_vertical_edge = (
            abs(start.x - end.x) < pcbnew.FromMM(0.01)
            and (
                abs(start.x - pcbnew.FromMM(91.0)) < pcbnew.FromMM(0.01)
                or abs(start.x - pcbnew.FromMM(109.0)) < pcbnew.FromMM(0.01)
            )
        )
        if is_vertical_edge:
            u1.Remove(graphic)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)

print(f"Updated: {BOARD_PATH}")
print(f"Backup:  {BACKUP_PATH}")
print("Added eleven GND vias and one 3V3 via; refilled F.Cu/B.Cu GND zones")
for net_name, width in widths_mm.items():
    count = sum(
        1
        for item in routing_items
        if item.Type() == pcbnew.PCB_TRACE_T and item.GetNetname() == net_name
    )
    if count:
        print(f"{net_name}: {count} segment(s) at {width:.2f} mm")
