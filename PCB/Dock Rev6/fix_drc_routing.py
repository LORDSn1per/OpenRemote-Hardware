#!/usr/bin/env python3
"""Reroute the Dock Rev6 tracks that caused shorts/0.15 mm clearances."""

from pathlib import Path
import shutil
import sys

sys.path.insert(
    0,
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/site-packages",
)
import pcbnew  # noqa: E402


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-drc-reroute.kicad_pcb"


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def add_track(board, net, layer, start, end, width):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(layer)
    track.SetNet(net)
    board.Add(track)


def main() -> None:
    if not BACKUP_PATH.exists():
        shutil.copy2(BOARD_PATH, BACKUP_PATH)

    board = pcbnew.LoadBoard(str(BOARD_PATH))

    # Hide mounting-hole designators from the finished silkscreen.
    for reference in ("H3", "H4"):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"{reference} not found")
        footprint.Reference().SetVisible(False)

    nets = {}
    for track in board.GetTracks():
        nets.setdefault(track.GetNetname(), track.GetNet())

    # Replace RF_SCK's diagonal B.Cu route with a clean F.Cu path through the
    # corridor between the ESP32 pads and the right-angle button hardware.
    rf_sck = [
        ((107.62, 81.12), (110.50, 81.12)),
        ((110.50, 81.12), (110.50, 90.01)),
        ((110.50, 90.01), (105.20, 90.01)),
        ((105.20, 90.01), (105.20, 94.00)),
        ((105.20, 94.00), (102.50, 96.70)),
        ((102.50, 96.70), (99.50, 96.70)),
        ((99.50, 96.70), (98.23, 97.97)),
        ((98.23, 97.97), (98.23, 98.88)),
    ]
    for start, end in rf_sck:
        add_track(board, nets["RF_SCK"], pcbnew.F_Cu, start, end, 0.20)

    # Move the +5 V trunk 0.244 mm left, giving the nearby +3V3 via and track
    # comfortable clearance while keeping the existing 0.30 mm power width.
    plus5 = [
        ((107.62, 73.50), (104.70, 76.42)),
        ((104.70, 76.42), (104.70, 86.038478)),
        ((104.70, 86.038478), (106.011522, 87.35)),
    ]
    for start, end in plus5:
        add_track(board, nets["+5V"], pcbnew.F_Cu, start, end, 0.30)

    # Shift the two IR_K vertical trunks 0.20 mm away from the adjacent 1 W
    # resistor pads.  All existing endpoints and the 0.30 mm width are kept.
    ir_k = [
        ((89.20, 109.975), (81.25, 102.225)),
        ((89.20, 109.975), (89.20, 123.0)),
        ((85.0, 127.0), (89.20, 123.0)),
        ((89.20, 123.0), (89.20, 124.498679)),
        ((92.5, 127.998679), (89.20, 124.498679)),
        ((119.0, 104.775), (114.20, 109.775)),
        ((114.20, 109.775), (114.20, 126.5)),
        ((113.5, 126.0), (114.20, 126.5)),
        ((114.20, 126.5), (114.20, 127.498679)),
        ((114.20, 127.498679), (114.20, 136.5)),
    ]
    for start, end in ir_k:
        add_track(board, nets["IR_K"], pcbnew.F_Cu, start, end, 0.30)

    remove_uuids = {
        # RF_SCK
        "0ad92fb5-9b89-419b-8840-b2f2f8d64238",
        "ade679d5-0c92-4a68-88a5-c27079e9a77f",
        # +5 V
        "0177b8c9-809c-4452-8935-a54ab63d7021",
        "36cd4693-d0aa-413e-ba0d-82fa722d2c9a",
        "9c541c26-ce8c-43ff-b0cd-d343d6ae4bd7",
        # Left IR_K trunk
        "6221530b-e595-43f6-87fe-1292208da3d9",
        "cd566052-1865-4e97-bfa0-d316a1c51964",
        "629df743-2c56-4dd9-8764-45f1c94be999",
        "d43011c8-a82d-4916-85d3-36158b196f77",
        "4c8ee5bb-1f85-49b3-9278-7a850d2d769e",
        # Right IR_K trunk
        "22d51b1b-dc0c-4faf-84cd-ad164368808a",
        "15b1ce65-4e34-446a-8406-b9e65b0ea443",
        "a013cb0b-d7d2-407a-84c5-68e0bac79c7c",
        "19646bd9-4f9f-4cfe-8d7e-9087d181a78c",
        "15988d7b-b94b-42fc-bb46-f7360f52ffed",
    }
    found = set()
    for track in list(board.GetTracks()):
        uuid = track.m_Uuid.AsString()
        if uuid in remove_uuids:
            found.add(uuid)
            board.Remove(track)
    missing = remove_uuids - found
    if missing:
        raise RuntimeError(f"Expected tracks were not found: {sorted(missing)}")

    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"Updated {BOARD_PATH}; replaced {len(remove_uuids)} old track segments")


if __name__ == "__main__":
    main()
