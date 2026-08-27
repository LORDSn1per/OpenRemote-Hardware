#!/usr/bin/env python3
"""Generate the Dock Rev6 controller schematic.

Requires kiutils. The resulting file is upgraded by KiCad after generation so
the checked-in schematic always uses the locally installed KiCad file format.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from kiutils.items.common import Effects, Font, PageSettings, Position, Property, Stroke, TitleBlock
from kiutils.items.schitems import (
    Connection,
    HierarchicalSheetInstance,
    LocalLabel,
    NoConnect,
    SchematicSymbol,
    SymbolProjectInstance,
    SymbolProjectPath,
    Text,
)
from kiutils.schematic import Schematic
from kiutils.symbol import Symbol, SymbolLib


HERE = Path(__file__).resolve().parent
OUT = HERE / "Dock Rev6.kicad_sch"
CUSTOM_LIB = HERE / "project_libraries" / "symbols" / "DockRev6.kicad_sym"
KICAD_SYMBOLS = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
PROJECT_NAME = "Dock Rev6"


def uid() -> str:
    return str(uuid4())


def snap(value: float) -> float:
    """Snap schematic origins to KiCad's 50 mil connection grid."""
    return round(value / 1.27) * 1.27


def font_effects(hide: bool = False, size: float = 1.27, bold: bool = False) -> Effects:
    return Effects(font=Font(width=size, height=size, bold=bold), hide=hide)


def property_at(key: str, value: str, x: float, y: float, hide: bool = False) -> Property:
    return Property(
        key=key,
        value=value,
        position=Position(X=x, Y=y, angle=0),
        effects=font_effects(hide=hide),
    )


def placed_property(source: Symbol, key: str, value: str, x: float, y: float, hide: bool) -> Property:
    template = next((p for p in source.properties if p.key == key), None)
    if template is None:
        return property_at(key, value, x, y, hide)
    effects = deepcopy(template.effects) if template.effects is not None else font_effects()
    effects.hide = hide
    return Property(
        key=key,
        value=value,
        position=Position(
            X=x + template.position.X,
            Y=y - template.position.Y,
            angle=template.position.angle or 0,
        ),
        effects=effects,
    )


def all_pins(symbol: Symbol):
    pins = list(symbol.pins)
    for unit in symbol.units:
        pins.extend(all_pins(unit))
    return pins


custom = SymbolLib.from_file(str(CUSTOM_LIB))
device = SymbolLib.from_file(str(KICAD_SYMBOLS / "Device.kicad_sym"))
power = SymbolLib.from_file(str(KICAD_SYMBOLS / "power.kicad_sym"))

source_symbols: dict[str, Symbol] = {}
for nickname, library in (("DockRev6", custom), ("Device", device), ("power", power)):
    for symbol in library.symbols:
        source_symbols[f"{nickname}:{symbol.entryName}"] = symbol


schematic = Schematic.create_new()
schematic.uuid = uid()
schematic.paper = PageSettings(paperSize="A4")
schematic.titleBlock = TitleBlock(
    title="OpenRemote Charging Dock Controller",
    date="2026-08-25",
    revision="6",
    company="OpenRemote",
    comments={1: "ESP32-C3 Super Mini + CC1101 + four-channel parallel IR emitter bank"},
)
schematic.sheetInstances = [HierarchicalSheetInstance(instancePath="/", page="1")]

embedded: set[str] = set()
placed: dict[str, tuple[SchematicSymbol, Symbol]] = {}


def add_symbol(
    lib_id: str,
    reference: str,
    value: str,
    x: float,
    y: float,
    footprint: str | None = None,
    datasheet: str | None = None,
    description: str | None = None,
) -> SchematicSymbol:
    x, y = snap(x), snap(y)
    source = source_symbols[lib_id]
    if lib_id not in embedded:
        embedded_symbol = deepcopy(source)
        embedded_symbol.libId = lib_id
        schematic.libSymbols.append(embedded_symbol)
        embedded.add(lib_id)

    defaults = {p.key: p.value for p in source.properties}
    footprint = defaults.get("Footprint", "") if footprint is None else footprint
    datasheet = defaults.get("Datasheet", "") if datasheet is None else datasheet
    description = defaults.get("Description", "") if description is None else description

    item = SchematicSymbol(
        position=Position(X=x, Y=y, angle=0),
        unit=1,
        inBom=not reference.startswith("#"),
        onBoard=not reference.startswith("#"),
        dnp=False,
        uuid=uid(),
    )
    item.libId = lib_id
    item.properties = [
        placed_property(source, "Reference", reference, x, y, reference.startswith("#")),
        placed_property(source, "Value", value, x, y, False),
        placed_property(source, "Footprint", footprint, x, y, True),
        placed_property(source, "Datasheet", datasheet, x, y, True),
        placed_property(source, "Description", description, x, y, True),
    ]
    for pin in all_pins(source):
        item.pins.setdefault(str(pin.number), uid())
    item.instances = [
        SymbolProjectInstance(
            name=PROJECT_NAME,
            paths=[SymbolProjectPath(sheetInstancePath="/", reference=reference, unit=1)],
        )
    ]
    schematic.schematicSymbols.append(item)
    placed[reference] = (item, source)
    return item


def pin_xy(reference: str, number: str) -> tuple[float, float, int]:
    item, source = placed[reference]
    pin = next(p for p in all_pins(source) if str(p.number) == str(number))
    return item.position.X + pin.position.X, item.position.Y - pin.position.Y, pin.position.angle or 0


def label_pin(reference: str, number: str, net: str) -> None:
    x, y, angle = pin_xy(reference, number)
    if angle == 0:
        target = Position(X=x - 7.62, Y=y)
        label_angle = 180
    elif angle == 180:
        target = Position(X=x + 7.62, Y=y)
        label_angle = 0
    else:
        # Turn vertical passive/power pins sideways so net labels stay readable.
        target = Position(X=x + 7.62, Y=y)
        label_angle = 0
    schematic.graphicalItems.append(
        Connection(
            type="wire",
            points=[Position(X=x, Y=y), target],
            stroke=Stroke(width=0),
            uuid=uid(),
        )
    )
    schematic.labels.append(
        LocalLabel(
            text=net,
            position=Position(X=target.X, Y=target.Y, angle=label_angle),
            effects=font_effects(),
            uuid=uid(),
        )
    )


def no_connect(reference: str, number: str) -> None:
    x, y, _ = pin_xy(reference, number)
    schematic.noConnects.append(NoConnect(position=Position(X=x, Y=y), uuid=uid()))


def heading(text: str, x: float, y: float) -> None:
    schematic.texts.append(
        Text(
            text=text,
            position=Position(X=x, Y=y, angle=0),
            effects=font_effects(size=1.8, bold=True),
            uuid=uid(),
        )
    )


def note(text: str, x: float, y: float) -> None:
    schematic.texts.append(
        Text(
            text=text,
            position=Position(X=x, Y=y, angle=0),
            effects=font_effects(size=1.27),
            uuid=uid(),
        )
    )


# Controller and input power
heading("CONTROLLER / POWER", 32, 25)
add_symbol("DockRev6:HX-XH2.54-2PZZ", "J1", "5V INPUT", 42, 42)
label_pin("J1", "1", "+5V")
label_pin("J1", "2", "GND")

add_symbol("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 42, 78)
label_pin("#FLG01", "1", "+5V")
add_symbol("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 55, 78)
label_pin("#FLG02", "1", "GND")

add_symbol("DockRev6:ESP32-C3_SuperMini", "U1", "ESP32-C3 Super Mini", 82, 58)
for pin, net in {
    "5V": "+5V",
    "GND": "GND",
    "3V3": "+3V3",
    "4": "RF_SCK",
    "5": "RF_MISO",
    "6": "RF_MOSI",
    "7": "RF_CSN",
    "10": "RF_GDO0",
    "20": "RF_GDO2",
    "0": "IR_PWM",
    "1": "STATUS_LED",
    "3": "BUTTON",
}.items():
    label_pin("U1", pin, net)
for pin in ("2", "8", "9", "21"):
    no_connect("U1", pin)

# ESP input decoupling
add_symbol("Device:C", "C1", "100nF", 112, 40, "Capacitor_SMD:C_0603_1608Metric")
label_pin("C1", "1", "+5V")
label_pin("C1", "2", "GND")
add_symbol("Device:C", "C2", "10uF", 124, 40, "Capacitor_SMD:C_0805_2012Metric")
label_pin("C2", "1", "+5V")
label_pin("C2", "2", "GND")

# CC1101 radio and local decoupling
heading("433 MHz RADIO", 152, 25)
add_symbol("DockRev6:CC1101_433MHz_Coil", "U2", "CC1101 433MHz COIL", 174, 50)
for pin, net in {
    "1": "GND",
    "2": "+3V3",
    "3": "RF_GDO0",
    "4": "RF_CSN",
    "5": "RF_SCK",
    "6": "RF_MOSI",
    "7": "RF_MISO",
    "8": "RF_GDO2",
}.items():
    label_pin("U2", pin, net)
add_symbol("Device:C", "C3", "100nF", 207, 41, "Capacitor_SMD:C_0603_1608Metric")
label_pin("C3", "1", "+3V3")
label_pin("C3", "2", "GND")
add_symbol("Device:C", "C4", "10uF", 219, 41, "Capacitor_SMD:C_0805_2012Metric")
label_pin("C4", "1", "+3V3")
label_pin("C4", "2", "GND")

# User interface
heading("BUTTON / STATUS", 32, 100)
add_symbol("DockRev6:SW_6x6x5H", "SW1", "6x6x5H TACTILE", 70, 119)
label_pin("SW1", "1", "BUTTON")
label_pin("SW1", "2", "GND")
add_symbol("Device:R", "R1", "10k", 42, 120, "Resistor_SMD:R_0603_1608Metric")
label_pin("R1", "1", "+3V3")
label_pin("R1", "2", "BUTTON")
add_symbol("Device:C", "C5", "100nF", 55, 120, "Capacitor_SMD:C_0603_1608Metric")
label_pin("C5", "1", "BUTTON")
label_pin("C5", "2", "GND")

add_symbol("Device:R", "R2", "1k", 112, 120, "Resistor_SMD:R_0603_1608Metric")
label_pin("R2", "1", "STATUS_LED")
label_pin("R2", "2", "GREEN_A")
add_symbol("DockRev6:LED_5mm_Green", "D5", "GREEN 5mm", 140, 124)
label_pin("D5", "2", "GREEN_A")
label_pin("D5", "1", "GND")

# IR gate drive. Both halves of the FS8205A are paralleled.
heading("PARALLEL IR EMITTER BANK", 152, 100)
note("D1-D4: MHL512IR059CRT 940nm; R5-R8: 39R 0.5W each", 185, 106)
note("IR_PWM is pulse-only: approximately 95mA per LED from 5V", 185, 110)
add_symbol("Device:R", "R3", "100R", 163, 121, "Resistor_SMD:R_0603_1608Metric")
label_pin("R3", "1", "IR_PWM")
label_pin("R3", "2", "IR_GATE")
add_symbol("Device:R", "R4", "100k", 177, 121, "Resistor_SMD:R_0603_1608Metric")
label_pin("R4", "1", "IR_GATE")
label_pin("R4", "2", "GND")
add_symbol(
    "DockRev6:FS8205A",
    "Q1",
    "FS8205A",
    207,
    121,
    datasheet="https://www.lcsc.com/datasheet/lcsc_datasheet_2010271837_FUXINSEMI-FS8205A_C908265.pdf",
)
for pin in ("1", "3"):
    label_pin("Q1", pin, "GND")
for pin in ("2", "4"):
    label_pin("Q1", pin, "IR_GATE")
for pin in ("5", "6"):
    label_pin("Q1", pin, "IR_K")

# Each LED is parallel, but has its own resistor for balanced current sharing.
ir_datasheet = "https://datasheet.lcsc.com/datasheet/pdf/29b83153b84e1380900c8f5ca89a30c7.pdf?productCode=C405273"
for index, y in enumerate((142.24, 154.94, 167.64, 180.34), start=1):
    led_ref = f"D{index}"
    resistor_ref = f"R{index + 4}"
    branch_net = f"IR_A{index}"
    led_item = add_symbol("DockRev6:MHL512IR059CRT", led_ref, "MHL512IR059CRT 940nm", 135, y, datasheet=ir_datasheet)
    next(p for p in led_item.properties if p.key == "Value").effects.hide = True
    label_pin(led_ref, "1", "IR_K")
    label_pin(led_ref, "2", branch_net)
    resistor_item = add_symbol(
        "Device:R",
        resistor_ref,
        "39R 0.5W",
        160,
        y,
        "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P15.24mm_Horizontal",
    )
    next(p for p in resistor_item.properties if p.key == "Value").effects.hide = True
    label_pin(resistor_ref, "1", "+5V")
    label_pin(resistor_ref, "2", branch_net)

# Local energy storage for the pulsed IR bank.
add_symbol("Device:C", "C6", "100uF", 252, 145, "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm")
label_pin("C6", "1", "+5V")
label_pin("C6", "2", "GND")
add_symbol("Device:C", "C7", "100nF", 265, 145, "Capacitor_SMD:C_0603_1608Metric")
label_pin("C7", "1", "+5V")
label_pin("C7", "2", "GND")

schematic.to_file(str(OUT))
print(f"Generated {OUT}")
print(f"Placed {len(schematic.schematicSymbols)} symbols and {len(schematic.labels)} net labels")
