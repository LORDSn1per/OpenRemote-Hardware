#!/usr/bin/env python3
"""Replace Dock Rev6 SW1 with Kinghelm KH-6X6X5H-ZJ (LCSC C2837541)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-c2837541-switch.kicad_pcb"
FOOTPRINT_DIR = ROOT / "project_libraries/footprints/DockRev6.pretty"
FOOTPRINT_NAME = "SW-TH_KH-6X6X5H-ZJ"


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def close(a: pcbnew.VECTOR2I, b: pcbnew.VECTOR2I, tolerance_mm: float = 0.02) -> bool:
    tolerance = pcbnew.FromMM(tolerance_mm)
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance


def find_track(
    tracks: list,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> pcbnew.PCB_TRACK:
    start_point = point(*start)
    end_point = point(*end)
    for track in tracks:
        if track.Type() != pcbnew.PCB_TRACE_T or track.GetNetname() != net_name:
            continue
        forward = close(track.GetStart(), start_point) and close(track.GetEnd(), end_point)
        reverse = close(track.GetStart(), end_point) and close(track.GetEnd(), start_point)
        if forward or reverse:
            return track
    raise RuntimeError(f"Track not found: {net_name} {start} -> {end}")


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float = 0.20,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetLayer(layer)
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetNet(board.FindNet(net_name))
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    position: tuple[float, float],
    diameter_mm: float = 0.60,
    drill_mm: float = 0.30,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(*position))
    via.SetWidth(pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(drill_mm))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet(net_name))
    board.Add(via)


if not BACKUP_PATH.exists():
    shutil.copy2(BOARD_PATH, BACKUP_PATH)

board = pcbnew.LoadBoard(str(BOARD_PATH))
old_switch = board.FindFootprintByReference("SW1")
if old_switch is None:
    raise RuntimeError("SW1 was not found")
tracks = list(board.GetTracks())

# Remove the old vertical-switch fanout and the RF_MOSI diagonal that crosses
# the exact C2837541 left support hole.
tracks_to_remove = []
for net_name, old_start, old_end in (
    ("BUTTON", (96.5, 76.0), (103.0, 76.0)),
    ("BUTTON", (103.0, 76.0), (106.144265, 79.144265)),
    ("BUTTON", (96.5, 76.0), (95.140001, 77.359999)),
    ("BUTTON", (95.140001, 77.359999), (95.140001, 92.8)),
    ("RF_MOSI", (93.878478, 76.04), (106.5, 88.661522)),
):
    tracks_to_remove.append(find_track(tracks, net_name, old_start, old_end))
for old_track in tracks_to_remove:
    board.Remove(old_track)
board.Remove(old_switch)

switch = pcbnew.FootprintLoad(str(FOOTPRINT_DIR), FOOTPRINT_NAME)
if switch is None:
    raise RuntimeError(f"Unable to load {FOOTPRINT_NAME}")

# The actuator faces the rear.  Its footprint nose finishes at Y=71.95 mm,
# aligned to the rear Edge.Cuts, while the switch body and all four holes stay
# on the PCB tongue.
switch.SetReference("SW1")
switch.SetValue("KH-6X6X5H-ZJ")
switch.SetPosition(point(100.00, 78.17))
switch.SetOrientationDegrees(180.0)
switch.SetFPID(pcbnew.LIB_ID("DockRev6", FOOTPRINT_NAME))
for field in switch.GetFields():
    if field.GetName() == "Description":
        field.SetText(
            "Kinghelm KH-6X6X5H-ZJ (LCSC C2837541), "
            "SPST right-angle 6x6mm 5H THT tactile switch"
        )
board.Add(switch)

for pad in switch.Pads():
    if pad.GetNumber() == "1":
        pad.SetNet(board.FindNet("BUTTON"))
    elif pad.GetNumber() == "2":
        pad.SetNet(board.FindNet("GND"))

# BUTTON fanout on B.Cu, clear of the 1.30 mm support holes.
button_pad = (102.25, 76.92)
for start, end in (
    (button_pad, (104.00, 77.50)),
    ((104.00, 77.50), (106.144265, 79.144265)),
    (button_pad, (101.00, 78.17)),
    ((101.00, 78.17), (101.00, 81.50)),
    ((101.00, 81.50), (96.50, 81.50)),
    ((96.50, 81.50), (95.140001, 82.859999)),
    ((95.140001, 82.859999), (95.140001, 92.80)),
):
    add_track(board, "BUTTON", pcbnew.B_Cu, start, end)

# Connect contact 2 to the already-stitched rear B.Cu GND region.
add_via(board, "GND", (95.50, 74.67))
add_via(board, "GND", (103.00, 82.50))
add_track(board, "GND", pcbnew.B_Cu, (97.75, 76.92), (96.75, 75.92), 0.25)
add_track(board, "GND", pcbnew.B_Cu, (96.75, 75.92), (95.50, 74.67), 0.25)

# Detour RF_MOSI through the narrow, datasheet-defined gap between contact 2
# and support pad 4, then rejoin the existing RF routing.
rf_mosi_points = (
    (93.878478, 76.04),
    (97.50, 78.45),
    (97.80, 78.90),
    (98.05, 80.65),
    (98.05, 80.80),
    (103.00, 86.40),
    (106.50, 88.661522),
)
for start, end in zip(rf_mosi_points, rf_mosi_points[1:]):
    add_track(board, "RF_MOSI", pcbnew.F_Cu, start, end)

# Preserve the required neck-down beside the existing 3V3 via.
for track in board.GetTracks():
    if track.Type() != pcbnew.PCB_TRACE_T or track.GetNetname() != "+5V":
        continue
    if close(track.GetStart(), point(104.944265, 76.175735)) and close(
        track.GetEnd(), point(104.944265, 86.282743)
    ):
        track.SetWidth(pcbnew.FromMM(0.20))

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(BOARD_PATH), board)

print(f"Updated {BOARD_PATH}")
print(f"Backup  {BACKUP_PATH}")
print("SW1: Kinghelm KH-6X6X5H-ZJ / C2837541, rear-facing at (100.00, 78.17) mm")
