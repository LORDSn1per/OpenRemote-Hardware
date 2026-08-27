import adsk.core
import adsk.fusion
import json
import os


OUTPUT = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware/PCB/Dock Rev6/project_libraries/3D-models/ESP32-C3_SuperMini_2x08_Header.step"
TEMP_NAME = "TEMP ESP32-C3 2x08 Header Export"


def _box(manager, cx, cy, cz, sx, sy, sz):
    obb = adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(cx / 10, cy / 10, cz / 10),
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0),
        sx / 10,
        sy / 10,
        sz / 10,
    )
    return manager.createBox(obb)


def _appearance(app, design, name):
    for appearance in design.appearances:
        if appearance.name == name:
            return appearance
    for library in app.materialLibraries:
        for appearance in library.appearances:
            if appearance.name == name:
                if not appearance.copyTo(design):
                    raise RuntimeError("Could not copy appearance: " + name)
                for copied in design.appearances:
                    if copied.name == name:
                        return copied
    raise RuntimeError("Appearance not found: " + name)


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise RuntimeError("Active Fusion document is not a Design")
    root = design.rootComponent
    old = next((o for o in root.occurrences if o.component.name == TEMP_NAME), None)
    if old:
        old.deleteMe()

    occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = TEMP_NAME
    manager = adsk.fusion.TemporaryBRepManager.get()
    feature = component.features.baseFeatures.add()
    feature.name = "ESP32-C3 Bottom Header Geometry"
    feature.startEdit()
    black = _appearance(app, design, "Plastic - Matte (Black)")
    gold = _appearance(app, design, "Gold - Polished")

    for row, x in enumerate((-7.62, 7.62), 1):
        strip = component.bRepBodies.add(_box(manager, x, 0, 1.12, 2.5, 20.32, 2.24), feature)
        strip.name = "Black Plastic Header Strip {}".format(row)
        strip.appearance = black
        for index in range(8):
            y = -8.89 + 2.54 * index
            # Trimmed pin: 1.7 mm through the carrier/host PCB and 3.7 mm
            # toward the module.  This avoids the base-lid collision of a
            # stock 11.6 mm male-header model.
            pin = component.bRepBodies.add(_box(manager, x, y, 1.0, 0.64, 0.64, 5.4), feature)
            pin.name = "Gold Pin {}-{}".format(row, index + 1)
            pin.appearance = gold
    feature.finishEdit()

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    exporter = design.exportManager
    options = exporter.createSTEPExportOptions(OUTPUT, component)
    if not options or not exporter.execute(options):
        raise RuntimeError("Could not export ESP32 header STEP")
    solid_count = component.bRepBodies.count
    occurrence.deleteMe()
    design.computeAll()
    print(json.dumps({
        "step": OUTPUT,
        "solid_count": solid_count,
        "black_plastic_height_mm": 2.24,
        "trimmed_pin_span_mm": [-1.7, 3.7],
    }, indent=2))
