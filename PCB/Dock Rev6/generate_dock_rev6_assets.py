#!/usr/bin/env python3
"""Generate the self-contained Dock Rev6 KiCad libraries and custom STEP models."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIB = ROOT / "project_libraries"
PRETTY = LIB / "footprints" / "DockRev6.pretty"
MODELS = LIB / "3D-models"
SYMBOLS = LIB / "symbols"

KICAD = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")
FP_STD = KICAD / "footprints"
MODEL_STD = KICAD / "3dmodels"
REMOTE_REV6 = ROOT.parent / "Revision 6" / "project_libraries"


def uid() -> str:
    return str(uuid.uuid4())


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def localize_footprint(src: Path, dst_name: str, model_name: str, description: str) -> None:
    text = src.read_text(encoding="utf-8")
    first = text.splitlines()[0]
    old_name = first.split('"')[1]
    text = text.replace(f'(footprint "{old_name}"', f'(footprint "{dst_name}"', 1)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("(descr "):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f'{indent}(descr "{description}")'
            break
    text = "\n".join(lines) + "\n"
    # Replace whichever stock model was supplied with the self-contained project model.
    start = text.find("\t(model ")
    if start < 0:
        start = text.find("  (model ")
    if start >= 0:
        q1 = text.find('"', start)
        q2 = text.find('"', q1 + 1)
        text = text[: q1 + 1] + f"${{KIPRJMOD}}/project_libraries/3D-models/{model_name}" + text[q2:]
    write(PRETTY / f"{dst_name}.kicad_mod", text)


def fp_header(name: str, reference: str, description: str, tags: str) -> list[str]:
    return [
        f'(footprint "{name}"',
        '\t(version 20240108)',
        '\t(generator "pcbnew")',
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        f'\t(descr "{description}")',
        f'\t(tags "{tags}")',
        f'\t(property "Reference" "{reference}" (at 0 -14 0) (layer "F.SilkS") (uuid "{uid()}")',
        '\t\t(effects (font (size 1 1) (thickness 0.15))))',
        f'\t(property "Value" "{name}" (at 0 14 0) (layer "F.Fab") (uuid "{uid()}")',
        '\t\t(effects (font (size 1 1) (thickness 0.15))))',
        f'\t(property "Footprint" "" (at 0 0 0) (unlocked yes) (layer "F.Fab") (hide yes) (uuid "{uid()}")',
        '\t\t(effects (font (size 1.27 1.27))))',
        f'\t(property "Datasheet" "" (at 0 0 0) (unlocked yes) (layer "F.Fab") (hide yes) (uuid "{uid()}")',
        '\t\t(effects (font (size 1.27 1.27))))',
        f'\t(property "Description" "{description}" (at 0 0 0) (unlocked yes) (layer "F.Fab") (hide yes) (uuid "{uid()}")',
        '\t\t(effects (font (size 1.27 1.27))))',
        '\t(attr through_hole)',
    ]


def fp_line(x1: float, y1: float, x2: float, y2: float, layer: str, width: float) -> str:
    return (
        f'\t(fp_line (start {x1:g} {y1:g}) (end {x2:g} {y2:g}) '
        f'(stroke (width {width:g}) (type solid)) (layer "{layer}") (uuid "{uid()}"))'
    )


def fp_text(text: str, x: float, y: float, layer: str = "F.Fab", size: float = 0.65) -> str:
    return (
        f'\t(fp_text user "{text}" (at {x:g} {y:g}) (layer "{layer}") (uuid "{uid()}") '
        f'(effects (font (size {size:g} {size:g}) (thickness 0.1))))'
    )


def pad(number: int | str, x: float, y: float, pin1: bool = False) -> str:
    shape = "rect" if pin1 else "circle"
    return (
        f'\t(pad "{number}" thru_hole {shape} (at {x:g} {y:g}) (size 1.9 1.9) '
        f'(drill 1) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{uid()}"))'
    )


def model_block(
    filename: str,
    offset: tuple[float, float, float] = (0, 0, 0),
    rotate: tuple[float, float, float] = (0, 0, 0),
) -> list[str]:
    ox, oy, oz = offset
    rx, ry, rz = rotate
    model_path = filename if filename.startswith("${") else f"${{KIPRJMOD}}/project_libraries/3D-models/{filename}"
    return [
        f'\t(model "{model_path}"',
        f'\t\t(offset (xyz {ox:g} {oy:g} {oz:g}))',
        '\t\t(scale (xyz 1 1 1))',
        f'\t\t(rotate (xyz {rx:g} {ry:g} {rz:g}))',
        '\t)',
    ]


def make_esp_footprint() -> None:
    name = "ESP32-C3_SuperMini_Header_2x08_P2.54mm"
    lines = fp_header(
        name,
        "U",
        "Generic ESP32-C3 Super Mini, 18x22.52mm, two 1x8 2.54mm header rows",
        "ESP32 C3 Super Mini module header 2.54mm",
    )
    # Board outline and USB overhang.
    for layer, width in (("F.SilkS", 0.15), ("F.Fab", 0.1), ("F.CrtYd", 0.05)):
        extra = 0.5 if layer == "F.CrtYd" else 0
        x0, x1 = -9 - extra, 9 + extra
        y0, y1 = -11.26 - extra, 11.26 + extra
        lines += [
            fp_line(x0, y0, x1, y0, layer, width), fp_line(x1, y0, x1, y1, layer, width),
            fp_line(x1, y1, x0, y1, layer, width), fp_line(x0, y1, x0, y0, layer, width),
        ]
    lines += [fp_line(-4.5, -11.26, 4.5, -11.26, "F.SilkS", 0.35)]
    # Use signal names as pad numbers to avoid inventing an ambiguous 1-16 numbering scheme.
    # Order is exactly the supplied module image, with USB-C at negative Y.
    left_names = ["5V", "GND", "3V3", "4", "3", "2", "1", "0"]
    right_names = ["5", "6", "7", "8", "9", "10", "20", "21"]
    aliases = {
        "4": "GPIO4/SCK/A4", "3": "GPIO3/A3", "2": "GPIO2/A2", "1": "GPIO1/A1", "0": "GPIO0/A0",
        "5": "GPIO5/MISO/A5", "6": "GPIO6/MOSI", "7": "GPIO7/SS", "8": "GPIO8/SDA",
        "9": "GPIO9/SCL", "10": "GPIO10", "20": "GPIO20/RX", "21": "GPIO21/TX",
    }
    ys = [-8.89 + 2.54 * i for i in range(8)]
    for index, (signal, y) in enumerate(zip(left_names, ys)):
        lines.append(pad(signal, -7.62, y, index == 0))
        label = signal if signal in ("5V", "GND", "3V3") else aliases[signal]
        lines.append(fp_text(label, -5.55, y, size=0.52))
    for signal, y in zip(right_names, ys):
        lines.append(pad(signal, 7.62, y))
        lines.append(fp_text(aliases[signal], 5.25, y, size=0.48))
    lines += [fp_text("ANTENNA KEEPOUT", 0, 9.0, "F.SilkS", 0.8)]
    # The supplied STEP uses a corner-based, landscape coordinate system.
    # Rotate it into the footprint's portrait orientation and centre its PCB.
    lines += model_block("ESP32-C3_SuperMini.step", offset=(-9, 11.26, 2.24), rotate=(0, 0, 90))
    lines += model_block("ESP32-C3_SuperMini_2x08_Header.step")
    lines.append(")")
    write(PRETTY / f"{name}.kicad_mod", "\n".join(lines) + "\n")


def make_cc1101_footprint() -> None:
    name = "CC1101_433MHz_Coil_Module_2x04_P2.54mm"
    lines = fp_header(
        name,
        "U",
        "CC1101 433MHz module with spring/coil antenna, 28x15mm PCB and 2x4 2.54mm header",
        "CC1101 433MHz RF transceiver spring coil antenna module",
    )
    # Origin is the 2x4 header centre; module body extends to the right.
    for layer, width in (("F.SilkS", 0.15), ("F.Fab", 0.1), ("F.CrtYd", 0.05)):
        # Courtyard includes both the PCB and the off-board spring antenna as one closed shape.
        if layer == "F.CrtYd":
            x0, x1, y0, y1 = -3.3, 44.0, -8.0, 8.0
        else:
            x0, x1, y0, y1 = -2.8, 25.2, -7.5, 7.5
        lines += [
            fp_line(x0, y0, x1, y0, layer, width), fp_line(x1, y0, x1, y1, layer, width),
            fp_line(x1, y1, x0, y1, layer, width), fp_line(x0, y1, x0, y0, layer, width),
        ]
    pin_names = ["GND", "VCC", "GDO0", "CSN", "SCK", "MOSI", "MISO/GDO1", "GDO2"]
    for row, y in enumerate((-3.81, -1.27, 1.27, 3.81)):
        left_num, right_num = row * 2 + 1, row * 2 + 2
        lines.append(pad(left_num, -1.27, y, left_num == 1))
        lines.append(pad(right_num, 1.27, y))
        lines.append(fp_text(pin_names[left_num - 1], 4.2, y - 0.35, size=0.5))
        lines.append(fp_text(pin_names[right_num - 1], 4.2, y + 0.35, size=0.5))
    lines += [
        fp_text("SPRING ANTENNA ->", 17.5, 0, "F.SilkS", 0.8),
    ]
    lines += model_block("CC1101_433MHz_Coil_Module.step")
    lines.append(")")
    write(PRETTY / f"{name}.kicad_mod", "\n".join(lines) + "\n")


def make_symbols() -> None:
    symbols = [
        ("ESP32-C3_SuperMini", "U", ["5V", "GND", "3V3", "4", "3", "2", "1", "0", "5", "6", "7", "8", "9", "10", "20", "21"], "DockRev6:ESP32-C3_SuperMini_Header_2x08_P2.54mm"),
        ("CC1101_433MHz_Coil", "U", ["GND", "VCC", "GDO0", "CSN", "SCK", "MOSI", "MISO/GDO1", "GDO2"], "DockRev6:CC1101_433MHz_Coil_Module_2x04_P2.54mm"),
        ("MHL512IR059CRT", "D", ["K", "A"], "DockRev6:LED_5mm_Side_Mount_C405273"),
        ("FS8205A", "Q", ["S1", "G1", "S2", "G2", "D2", "D1"], "DockRev6:FS8205A_SOT-23-6"),
        ("HX-XH2.54-2PZZ", "J", ["1", "2"], "DockRev6:HX-XH2.54-2PZZ_C42391660"),
        ("SW_6x6x5H", "SW", ["1", "2"], "DockRev6:SW_6x6x5H_THT"),
        ("LED_5mm_Green", "D", ["K", "A"], "DockRev6:LED_5mm_Green_THT"),
    ]
    out = ['(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor")']
    for name, ref, pins, footprint in symbols:
        height = max(7.62, (len(pins) // 2 + 1) * 2.54)
        top = height / 2
        # Give module pin names real breathing room. The ESP32 aliases are much
        # longer than ordinary IC pin names, and the CC1101 also needs more than
        # the generic 10.16 mm-wide body used by the small discrete symbols.
        if name == "ESP32-C3_SuperMini":
            half_width = 15.24
        elif name == "CC1101_433MHz_Coil":
            half_width = 10.16
        else:
            half_width = 5.08
        pin_x = half_width + 2.54
        out += [
            f'\t(symbol "{name}"',
            '\t\t(pin_names (offset 1.016))',
            '\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)',
            f'\t\t(property "Reference" "{ref}" (at 0 {top + 2.54:g} 0) (effects (font (size 1.27 1.27))))',
            f'\t\t(property "Value" "{name}" (at 0 {-top - 2.54:g} 0) (effects (font (size 1.27 1.27))))',
            f'\t\t(property "Footprint" "{footprint}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))',
            '\t\t(property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))',
            f'\t\t(property "Description" "Dock Rev6 project component: {name}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))',
            f'\t\t(symbol "{name}_0_1" (rectangle (start {-half_width:g} {top:g}) (end {half_width:g} {-top:g}) (stroke (width 0) (type default)) (fill (type background))))',
            f'\t\t(symbol "{name}_1_1"',
        ]
        left_count = (len(pins) + 1) // 2
        right_count = len(pins) - left_count
        for index, pin_name in enumerate(pins[:left_count], 1):
            y = (left_count - 1) * 1.27 - (index - 1) * 2.54
            is_supermini = name == "ESP32-C3_SuperMini"
            if name in ("HX-XH2.54-2PZZ", "LED_5mm_Green", "MHL512IR059CRT", "SW_6x6x5H"):
                etype = "passive"
            elif name == "FS8205A":
                etype = "input" if pin_name in ("G1", "G2") else "passive"
            elif is_supermini and pin_name == "3V3":
                etype = "power_out"
            else:
                etype = "power_in" if pin_name in ("GND", "VCC", "3V3", "5V") else "bidirectional"
            pin_number = pin_name if is_supermini else str(index)
            supermini_aliases = {"4": "GPIO4/SCK/A4", "3": "GPIO3/A3", "2": "GPIO2/A2", "1": "GPIO1/A1", "0": "GPIO0/A0"}
            display_name = pin_name if not is_supermini or pin_name in ("5V", "GND", "3V3") else supermini_aliases[pin_name]
            out.append(f'\t\t\t(pin {etype} line (at {-pin_x:g} {y:g} 0) (length 2.54) (name "{display_name}" (effects (font (size 1.27 1.27)))) (number "{pin_number}" (effects (font (size 1.27 1.27)))))')
        for rindex, pin_name in enumerate(pins[left_count:], left_count + 1):
            local = rindex - left_count - 1
            y = (right_count - 1) * 1.27 - local * 2.54
            is_supermini = name == "ESP32-C3_SuperMini"
            if name in ("HX-XH2.54-2PZZ", "LED_5mm_Green", "MHL512IR059CRT", "SW_6x6x5H"):
                etype = "passive"
            elif name == "FS8205A":
                etype = "input" if pin_name in ("G1", "G2") else "passive"
            elif is_supermini and pin_name == "3V3":
                etype = "power_out"
            else:
                etype = "power_in" if pin_name in ("GND", "VCC", "3V3", "5V") else "bidirectional"
            pin_number = pin_name if is_supermini else str(rindex)
            supermini_aliases = {"5": "GPIO5/MISO/A5", "6": "GPIO6/MOSI", "7": "GPIO7/SS", "8": "GPIO8/SDA", "9": "GPIO9/SCL", "10": "GPIO10", "20": "GPIO20/RX", "21": "GPIO21/TX"}
            display_name = supermini_aliases[pin_name] if is_supermini else pin_name
            out.append(f'\t\t\t(pin {etype} line (at {pin_x:g} {y:g} 180) (length 2.54) (name "{display_name}" (effects (font (size 1.27 1.27)))) (number "{pin_number}" (effects (font (size 1.27 1.27)))))')
        out += ['\t\t)', '\t)']
    out.append(')')
    write(SYMBOLS / "DockRev6.kicad_sym", "\n".join(out) + "\n")


def make_models() -> None:
    try:
        import cadquery as cq
        from cadquery import exporters
    except ImportError as exc:
        raise SystemExit("CadQuery is required to generate the two custom STEP models") from exc

    def colored_box(assy, name, size, center, color):
        x, y, z = size
        cx, cy, cz = center
        solid = cq.Workplane("XY").box(x, y, z).translate((cx, cy, cz))
        assy.add(solid, name=name, color=cq.Color(*color))

    # ESP32-C3_SuperMini.step is the owner's supplied model and is intentionally
    # not regenerated. Keeping it project-local makes KiCad independent of the
    # original Downloads path.
    if not (MODELS / "ESP32-C3_SuperMini.step").is_file():
        raise SystemExit("Missing supplied project model: ESP32-C3_SuperMini.step")

    # CC1101 433MHz spring antenna module. Origin matches the header centre in its footprint.
    cc = cq.Assembly(name="CC1101 433MHz Coil Module")
    cc_board = cq.Workplane("XY").box(28, 15, 1.0).translate((11.2, 0, 0.5))
    # Common module has two mechanical holes near the antenna end.
    for y in (-4.9, 4.9):
        cc_board = cc_board.faces(">Z").workplane().pushPoints([(21.0, y)]).hole(2.8)
    cc.add(cc_board, name="PCB", color=cq.Color(0.03, 0.18, 0.38))
    colored_box(cc, "CC1101", (6.2, 6.2, 1.0), (9.2, 0, 1.5), (0.06, 0.06, 0.06))
    colored_box(cc, "Crystal", (4.0, 2.5, 1.4), (15.5, -3.6, 1.7), (0.72, 0.72, 0.70))
    for index, (cx, cy) in enumerate(((15.0, 3.4), (18.2, 3.4), (18.5, 0), (14.8, -0.4))):
        colored_box(cc, f"RF component {index}", (2.0, 1.2, 0.8), (cx, cy, 1.4), (0.12, 0.12, 0.12))
    for row, y in enumerate((-3.81, -1.27, 1.27, 3.81)):
        for x in (-1.27, 1.27):
            colored_box(cc, f"Header pin {row} {x}", (0.64, 0.64, 7.0), (x, y, 0.5), (0.78, 0.62, 0.18))
            colored_box(cc, f"Header body {row} {x}", (2.45, 2.45, 2.5), (x, y, 2.25), (0.06, 0.06, 0.06))
    # Gold antenna launch pad and a physical helical 433MHz coil extending from the module.
    colored_box(cc, "Antenna pad", (3.5, 4.0, 0.25), (23.0, 0, 1.125), (0.82, 0.64, 0.12))
    helix = cq.Wire.makeHelix(1.8, 18.0, 2.3, cq.Vector(25.0, 0, 3.1), cq.Vector(1, 0, 0))
    coil = cq.Workplane("YZ", origin=(25.0, 0, 3.1)).circle(0.28).sweep(helix)
    cc.add(coil, name="433MHz spring antenna", color=cq.Color(0.65, 0.47, 0.18))
    cc.save(str(MODELS / "CC1101_433MHz_Coil_Module.step"))


def make_project_files() -> None:
    # Preserve the current KiCad 10 project settings while removing Rev6-specific board variants.
    source_pro = ROOT.parent / "Revision 6" / "OpenRemote.kicad_pro"
    project = json.loads(source_pro.read_text(encoding="utf-8"))
    project.setdefault("meta", {})["filename"] = "Dock Rev6.kicad_pro"
    project["meta"]["version"] = 1
    if isinstance(project.get("board"), dict):
        project["board"]["3dviewports"] = []
    project["net_settings"] = {"classes": [], "meta": {"version": 3}}
    write(ROOT / "Dock Rev6.kicad_pro", json.dumps(project, indent=2) + "\n")

    write(ROOT / "fp-lib-table", '''(fp_lib_table
  (version 7)
  (lib (name "DockRev6")(type "KiCad")(uri "${KIPRJMOD}/project_libraries/footprints/DockRev6.pretty")(options "")(descr "Dock Rev6 self-contained footprint library"))
  (lib (name "Capacitor_SMD")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Capacitor_SMD.pretty")(options "")(descr "KiCad standard SMD capacitors"))
  (lib (name "Capacitor_THT")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Capacitor_THT.pretty")(options "")(descr "KiCad standard through-hole capacitors"))
  (lib (name "Resistor_SMD")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Resistor_SMD.pretty")(options "")(descr "KiCad standard SMD resistors"))
  (lib (name "Resistor_THT")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Resistor_THT.pretty")(options "")(descr "KiCad standard through-hole resistors"))
)
''')
    write(ROOT / "sym-lib-table", '''(sym_lib_table
  (version 7)
  (lib (name "DockRev6")(type "KiCad")(uri "${KIPRJMOD}/project_libraries/symbols/DockRev6.kicad_sym")(options "")(descr "Dock Rev6 project symbols"))
  (lib (name "Device")(type "KiCad")(uri "${KICAD10_SYMBOL_DIR}/Device.kicad_sym")(options "")(descr "KiCad standard device symbols"))
  (lib (name "power")(type "KiCad")(uri "${KICAD10_SYMBOL_DIR}/power.kicad_sym")(options "")(descr "KiCad standard power symbols"))
)
''')
    schematic_path = ROOT / "Dock Rev6.kicad_sch"
    if not schematic_path.exists():
        write(schematic_path, f'''(kicad_sch
  (version 20231120)
  (generator "eeschema")
  (generator_version "10.0")
  (uuid "{uid()}")
  (paper "A4")
  (title_block (title "OpenRemote Charging Dock") (date "25 Aug 2026") (rev "6") (company "OpenRemote"))
  (lib_symbols)
  (sheet_instances (path "/" (page "1")))
  (embedded_fonts no)
)
''')


def make_readme() -> None:
    write(ROOT / "README.md", '''# OpenRemote Dock Rev6 KiCad Project

This is a self-contained KiCad 10 project starter for the OpenRemote Rev6 charging dock.

## Included footprints and 3D models

| Library footprint | Intended hardware | Interface / package |
|---|---|---|
| `ESP32-C3_SuperMini_Header_2x08_P2.54mm` | ESP32-C3 Super Mini shown by the owner | Two 1x8 headers, 2.54 mm pitch; owner-supplied STEP model |
| `CC1101_433MHz_Coil_Module_2x04_P2.54mm` | 28x15 mm CC1101 433 MHz module, spring antenna version | 2x4 header, 2.54 mm pitch |
| `LED_5mm_Side_Mount_C405273` | Meihua MHL512IR059CRT IR LED, LCSC C405273 | THT, 5 mm, horizontal/side mounting |
| `FS8205A_SOT-23-6` | FUXINSEMI FS8205A, LCSC C908265 | SOT-23-6 |
| `HX-XH2.54-2PZZ_C42391660` | hanxia HX-XH2.54-2PZZ, LCSC C42391660 | Vertical shrouded 1x2 male header; vendor land pattern is 2.50 mm pitch |
| `SW_6x6x5H_THT` | 6x6 mm tactile switch, 5 mm body height | Four-pin THT |
| `LED_5mm_Green_THT` | Standard green 5 mm LED | THT, 2.54 mm pitch |

The ESP32 model is the owner's supplied `esp32 c3 supermini.step`, copied into the project as `ESP32-C3_SuperMini.step`. All STEP files are project-local, so no Downloads or global KiCad 3D-model path is required.

## Important sourcing notes

- The ESP module follows the owner's supplied **16-pin ESP32-C3 Super Mini** image: 18x22.52 mm with two 1x8, 2.54 mm header rows. It does not use the different 18-pin Waveshare C3-Zero footprint from the earlier retail link.
- J1 is the exact hanxia HX-XH2.54-2PZZ sold as LCSC C42391660. LCSC describes it as 2.54 mm, but its manufacturer-linked EasyEDA land pattern uses 2.50 mm pad pitch, 1.0 mm drills, and a 7.5 x 5.9 mm shrouded body; the project follows that land pattern.
- CC1101 clone modules vary. This footprint follows the common 28x15 mm, 2x4 2.54 mm module and the pin order shown in the provided image. Check the delivered module before ordering the PCB.
- `Dock Rev6.kicad_pcb` now uses the Fusion handoff geometry: a 45x60 mm main body, 15 mm front/rear tongues, 92 mm overall length, and smooth blends. The tongues were narrowed from the nominal handoff width to maintain at least 1 mm clearance from the existing lid screw receivers.
- Four 3.3 mm NPTH M3 mounting holes are on an exact 37x52 mm pattern at dock X/Z `(+/-18.5, +6)` and `(+/-18.5, -46)`. Each hole has an R4 mm all-copper keepout and an 8 mm head-clearance reference circle.
- The matching Fusion base lid has four 7.5 mm OD bosses at those same centres. Each boss has a 2.55 mm blind pilot, an 8.0 mm PCB seating plane, and 3.4 mm thread engagement for an M3x5 screw through this 1.6 mm board. The original pre-boss lid body is retained hidden for rollback.

## Pin order

CC1101 pads are numbered by rows as shown in the supplied diagram: `1 GND`, `2 VCC`, `3 GDO0`, `4 CSN`, `5 SCK`, `6 MOSI`, `7 MISO/GDO1`, `8 GDO2`.

ESP32-C3 Super Mini pad numbers use the printed signal names directly. USB-C is at the top: left row `5V`, `GND`, `3V3`, `GPIO4/SCK/A4`, `GPIO3/A3`, `GPIO2/A2`, `GPIO1/A1`, `GPIO0/A0`; right row `GPIO5/MISO/A5`, `GPIO6/MOSI`, `GPIO7/SS`, `GPIO8/SDA`, `GPIO9/SCL`, `GPIO10`, `GPIO20/RX`, `GPIO21/TX`.

## Electrical design

- CC1101 SPI: `GPIO4 SCK`, `GPIO5 MISO`, `GPIO6 MOSI`, `GPIO7 CSN`; interrupts are `GPIO10 GDO0` and `GPIO20 GDO2`.
- Four MHL512IR059CRT emitters are connected in parallel through individual `39R 0.5W` resistors. GPIO0 drives both paralleled halves of Q1 through `100R`, with a `100k` gate pulldown.
- The 39R IR branches are designed for pulsed remote-control service at approximately 95mA per LED from 5V. Firmware must not hold `IR_PWM` high continuously.
- The green status LED uses GPIO1 and `1k`. The tactile button uses GPIO3 with a `10k` pull-up and `100nF` hardware debounce.
- ESP32-C3 strap pins GPIO2, GPIO8, and GPIO9 are deliberately left unconnected; GPIO21 is also reserved.
- Added decoupling: `100nF + 10uF` at the ESP 5V input, `100nF + 10uF` at the CC1101 3.3V rail, and `100uF + 100nF` at the pulsed IR bank.

### Capacitor placement

- `C1 100nF`: immediately beside U1's 5V/GND header pins; shortest possible loop.
- `C2 10uF`: beside U1 and C1 on the 5V rail; C1 should be closer than C2.
- `C3 100nF`: immediately beside U2 pins 2 VCC and 1 GND; this is the most placement-sensitive radio capacitor.
- `C4 10uF`: beside U2 and C3; C3 should be closer than C4.
- `C5 100nF`: beside U1 GPIO3 and pull-up R1, at the controller end of the BUTTON trace.
- `C6 100uF`: beside Q1/J1 at the high-current IR power entry/current loop.
- `C7 100nF`: beside Q1/J1 and C6, with the shortest 5V-to-GND loop; C7 should be closer to the switching loop than C6.

`Dock Rev6.kicad_pcb` is intentionally a blank mechanical board containing only the outline, four mounting holes, keepouts, and mechanical references. Populate it from the schematic with **Tools > Update PCB from Schematic** when component placement begins. The replaced component-staging board is retained as `Dock Rev6 Component Staging Backup.kicad_pcb`.

Regenerate the mechanical board with `generate_dock_rev6_mechanical_board.py`. `generate_preview_board.py` remains as a compatibility wrapper and generates the same mechanical board.
''')


def main() -> None:
    PRETTY.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    SYMBOLS.mkdir(parents=True, exist_ok=True)

    # Remove the superseded Waveshare C3-Zero assets from the earlier interpretation.
    for obsolete in (
        PRETTY / "ESP32-C3-Zero_Header_2x09_P2.54mm.kicad_mod",
        MODELS / "ESP32-C3-Zero_Header.step",
        MODELS / "ESP32-C3_SuperMini_Header.step",
    ):
        obsolete.unlink(missing_ok=True)

    make_esp_footprint()
    make_cc1101_footprint()

    # Reuse the exact IR LED footprint/model from the Rev6 remote build.
    ir_src = REMOTE_REV6 / "footprints" / "OpenRemoteLib.pretty" / "LED_5mm_Side_Mount.kicad_mod"
    ir_text = ir_src.read_text(encoding="utf-8")
    ir_text = ir_text.replace('(footprint "LED_5mm_Side_Mount"', '(footprint "LED_5mm_Side_Mount_C405273"', 1)
    ir_text = ir_text.replace('(property "Value" "SFH4346"', '(property "Value" "MHL512IR059CRT / C405273"', 1)
    write(PRETTY / "LED_5mm_Side_Mount_C405273.kicad_mod", ir_text)
    shutil.copy2(REMOTE_REV6 / "3D-models" / "Side Mount LED v1.step", MODELS / "Side Mount LED v1.step")

    localize_footprint(
        FP_STD / "Package_TO_SOT_SMD.pretty" / "SOT-23-6.kicad_mod",
        "FS8205A_SOT-23-6", "FS8205A_SOT-23-6.step",
        "FUXINSEMI FS8205A dual N-channel MOSFET, LCSC C908265, SOT-23-6L",
    )
    shutil.copy2(MODEL_STD / "Package_TO_SOT_SMD.3dshapes" / "SOT-23-6.step", MODELS / "FS8205A_SOT-23-6.step")

    # J1 uses vendor geometry imported from LCSC/EasyEDA and checked into the
    # project. Do not replace it with KiCad's generic 2.54 mm female socket.
    for vendor_asset in (
        PRETTY / "HX-XH2.54-2PZZ_C42391660.kicad_mod",
        MODELS / "HX-XH2.54-2PZZ_C42391660.step",
    ):
        if not vendor_asset.exists():
            raise FileNotFoundError(f"Missing vendor J1 asset: {vendor_asset}")

    localize_footprint(
        FP_STD / "Button_Switch_THT.pretty" / "SW_PUSH_6mm_H5mm.kicad_mod",
        "SW_6x6x5H_THT", "SW_6x6x5H_THT.step",
        "6x6mm through-hole tactile switch with 5mm body height",
    )
    shutil.copy2(MODEL_STD / "Button_Switch_THT.3dshapes" / "SW_PUSH_6mm_H5mm.step", MODELS / "SW_6x6x5H_THT.step")

    localize_footprint(
        FP_STD / "LED_THT.pretty" / "LED_D5.0mm.kicad_mod",
        "LED_5mm_Green_THT", "LED_5mm_Green.step",
        "Standard 5mm green through-hole LED, 2.54mm lead pitch",
    )
    shutil.copy2(MODEL_STD / "LED_THT.3dshapes" / "LED_D5.0mm_Green.step", MODELS / "LED_5mm_Green.step")

    make_symbols()
    make_models()
    make_project_files()
    make_readme()
    print(f"Generated Dock Rev6 assets in {ROOT}")


if __name__ == "__main__":
    main()
