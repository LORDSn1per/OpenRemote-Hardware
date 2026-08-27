#!/usr/bin/env python3
"""Apply the final Dock Rev6 LED footprints, placement, routing, and 3D links."""

from pathlib import Path
import shutil
import sys

KICAD_PY = Path("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/site-packages")
sys.path.insert(0, str(KICAD_PY))
import pcbnew  # noqa: E402


ROOT = Path(__file__).resolve().parent
BOARD_PATH = ROOT / "Dock Rev6.kicad_pcb"
BACKUP_PATH = ROOT / "Dock Rev6.before-final-led-update.kicad_pcb"
STD_LED_LIB = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/LED_SMD.pretty")


def mm(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def near(point: pcbnew.VECTOR2I, x: float, y: float, tol_mm: float = 0.002) -> bool:
    return abs(pcbnew.ToMM(point.x) - x) <= tol_mm and abs(pcbnew.ToMM(point.y) - y) <= tol_mm


def remove_front_led_routing(board: pcbnew.BOARD) -> None:
    old_anode = [(101.0, 162.0), (101.0, 155.175)]
    old_front_gnd_points = [
        (101.497057, 163.2),
        (99.66, 163.2),
        (98.46, 162.0),
        (102.2, 155.3),
        (102.2, 162.497057),
    ]
    for track in list(board.GetTracks()):
        net = track.GetNetname()
        start, end = track.GetStart(), track.GetEnd()
        if net == "Net-(D5-A)" and all(
            any(near(p, x, y) for x, y in old_anode) for p in (start, end)
        ):
            board.Remove(track)
        elif net == "GND" and any(near(start, x, y) for x, y in old_front_gnd_points) and any(
            near(end, x, y) for x, y in old_front_gnd_points
        ):
            board.Remove(track)


def add_track(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, start, end, width=0.25) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(mm(*start))
    track.SetEnd(mm(*end))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)


def replace_status_led(board: pcbnew.BOARD) -> None:
    old = board.FindFootprintByReference("D5")
    if old is None:
        raise RuntimeError("D5 was not found")
    old_path = old.GetPath()
    nets = {pad.GetNumber(): pad.GetNet() for pad in old.Pads()}

    footprint_io = pcbnew.PCB_IO_KICAD_SEXPR()
    led = footprint_io.FootprintLoad(str(STD_LED_LIB), "LED_0603_1608Metric", False)
    if led is None:
        raise RuntimeError("Could not load LED_SMD:LED_0603_1608Metric")
    led.SetReference("D5")
    led.SetValue("XL-1608UBC-04 BLUE")
    led.SetFPID(pcbnew.LIB_ID("DockRev6", "LED_0603_1608Metric_NoSilk"))
    led.SetField("Datasheet", "https://www.lcsc.com/product-detail/C965807.html")
    led.SetField("Description", "XINGLIGHT XL-1608UBC-04 blue 0603 SMD LED, LCSC C965807")
    led.SetField("LCSC", "C965807")
    led.SetField("Manufacturer", "XINGLIGHT")
    led.SetPath(old_path)
    led.SetPosition(mm(100.0, 165.05))
    led.SetOrientationDegrees(0.0)
    led.SetLayer(pcbnew.F_Cu)
    led.Reference().SetVisible(False)
    led.Value().SetVisible(False)
    for field in led.GetFields():
        field.SetVisible(False)
    # The status LED sits at the extreme front, so keep its assembly outline on
    # Fab rather than creating silkscreen collisions at the board edge.
    for graphic in led.GraphicalItems():
        if graphic.GetLayer() == pcbnew.F_SilkS:
            graphic.SetLayer(pcbnew.F_Fab)
    for pad in led.Pads():
        pad.SetNet(nets[pad.GetNumber()])

    remove_front_led_routing(board)
    board.Remove(old)
    board.Add(led)

    anode_net = nets["2"]
    add_track(board, anode_net, (101.0, 155.175), (101.0, 160.0))
    add_track(board, anode_net, (101.0, 160.0), (103.0, 162.0))
    add_track(board, anode_net, (103.0, 162.0), (103.0, 163.5))
    add_track(board, anode_net, (103.0, 163.5), (100.7875, 165.05))


def update_ir_led_models(board: pcbnew.BOARD) -> None:
    for reference in ("D1", "D2", "D3", "D4"):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"{reference} was not found")
        footprint.Models().clear()
        footprint.SetField(
            "Datasheet",
            "https://datasheet.lcsc.com/datasheet/pdf/29b83153b84e1380900c8f5ca89a30c7.pdf?productCode=C405273",
        )
        footprint.SetField("Description", "Dock Rev6 project component: MHL512IR059CRT")
        footprint.Reference().SetVisible(False)
        footprint.Value().SetVisible(False)

    # KiCad skips 3D-only empty mechanical footprints in some render/export
    # paths.  Carry the complete four-LED assembly on the real D1 THT
    # footprint instead.  The STEP origin is intentionally D1-relative.
    d1 = board.FindFootprintByReference("D1")
    d1.SetFPID(pcbnew.LIB_ID("DockRev6", "IR_LED_THT_D1_with_Assembly3D"))
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = "${KIPRJMOD}/project_libraries/3D-models/Dock_IR_LED_Assembly_25deg_3mm.step"
    d1.Add3DModel(model)


def add_ir_assembly_model(board: pcbnew.BOARD) -> None:
    old = board.FindFootprintByReference("IRLED3D1")
    if old is not None:
        board.Remove(old)


def main() -> None:
    if not BACKUP_PATH.exists():
        shutil.copy2(BOARD_PATH, BACKUP_PATH)
    stage = sys.argv[1] if len(sys.argv) > 1 else "all-non-destructive"
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    if stage == "status":
        replace_status_led(board)
    elif stage in ("ir", "all-non-destructive"):
        update_ir_led_models(board)
        add_ir_assembly_model(board)
    else:
        raise SystemExit("Use stage 'status' or 'ir'")
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"Updated {BOARD_PATH}")


if __name__ == "__main__":
    main()
