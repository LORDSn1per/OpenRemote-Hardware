import adsk.core
import adsk.fusion
import json
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
REPORT_PATH = os.path.join(WORKSPACE, "CAD", "Dock Rev6", "Charging Dock Rev6 Rear USB-C Fit v3 Report.json")

CENTRE_X_MM = -0.25
CENTRE_Y_MM = 11.73
WIDTH_MM = 12.0
HEIGHT_MM = 7.0
CORNER_RADIUS_MM = 1.0
OUTER_Z_MIN_MM = -75.0
OUTER_Z_MAX_MM = -63.0

# Concealed relief for the ESP32 module PCB and low rear-edge components.  It
# stops 0.8 mm inside the physical rear face, so only the USB opening is visible.
POCKET_X_MM = 0.0
POCKET_Y_MM = 9.85
POCKET_WIDTH_MM = 18.8
POCKET_HEIGHT_MM = 4.4
POCKET_Z_MIN_MM = -69.2
POCKET_Z_MAX_MM = -63.0


def _point_mm(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def _bbox_mm(box):
    return {
        "min_mm": [box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10],
        "max_mm": [box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10],
    }


def _box(manager, cx, cy, zmin, zmax, width, height):
    obb = adsk.core.OrientedBoundingBox3D.create(
        _point_mm(cx, cy, (zmin + zmax) / 2.0),
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0),
        width / 10.0,
        height / 10.0,
        (zmax - zmin) / 10.0,
    )
    return manager.createBox(obb)


def _rounded_cutter(manager):
    radius = CORNER_RADIUS_MM
    cutter = _box(manager, CENTRE_X_MM, CENTRE_Y_MM, OUTER_Z_MIN_MM, OUTER_Z_MAX_MM, WIDTH_MM - 2 * radius, HEIGHT_MM)
    vertical = _box(manager, CENTRE_X_MM, CENTRE_Y_MM, OUTER_Z_MIN_MM, OUTER_Z_MAX_MM, WIDTH_MM, HEIGHT_MM - 2 * radius)
    if not manager.booleanOperation(cutter, vertical, adsk.fusion.BooleanTypes.UnionBooleanType):
        raise RuntimeError("Could not build the rounded USB-C cutter")
    dx = WIDTH_MM / 2.0 - radius
    dy = HEIGHT_MM / 2.0 - radius
    for x_sign in (-1, 1):
        for y_sign in (-1, 1):
            cylinder = manager.createCylinderOrCone(
                _point_mm(CENTRE_X_MM + x_sign * dx, CENTRE_Y_MM + y_sign * dy, OUTER_Z_MIN_MM),
                radius / 10.0,
                _point_mm(CENTRE_X_MM + x_sign * dx, CENTRE_Y_MM + y_sign * dy, OUTER_Z_MAX_MM),
                radius / 10.0,
            )
            if not manager.booleanOperation(cutter, cylinder, adsk.fusion.BooleanTypes.UnionBooleanType):
                raise RuntimeError("Could not round a USB-C cutter corner")
    return cutter


def _add_body(component, body, name):
    feature = component.features.baseFeatures.add()
    feature.name = name + " Base Feature"
    feature.startEdit()
    added = component.bRepBodies.add(body, feature)
    feature.finishEdit()
    added.name = name
    return added


def _parameter(design, name, expression, units, comment):
    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        existing.comment = comment
        return
    design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), units, comment)


def run(context):
    try:
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active document is not a Fusion Design")
        root = design.rootComponent
        dock_occurrence = None
        for occurrence in root.occurrences:
            if occurrence.fullPathName == "Dock:1":
                dock_occurrence = occurrence
                break
        if not dock_occurrence:
            raise RuntimeError("Dock:1 was not found")
        component = dock_occurrence.component
        source = component.bRepBodies.itemByName("Dock Pre-USB-C Master Backup")
        if not source:
            source = component.bRepBodies.itemByName("Dock Pre-Rear-USB-C Backup")
        if not source:
            raise RuntimeError("The uncut dock master body was not found")

        manager = adsk.fusion.TemporaryBRepManager.get()
        replacement = manager.copy(source)
        outside = _rounded_cutter(manager)
        pocket = _box(
            manager, POCKET_X_MM, POCKET_Y_MM, POCKET_Z_MIN_MM, POCKET_Z_MAX_MM,
            POCKET_WIDTH_MM, POCKET_HEIGHT_MM,
        )
        if not manager.booleanOperation(replacement, outside, adsk.fusion.BooleanTypes.DifferenceBooleanType):
            raise RuntimeError("The rear USB-C cutter did not intersect the shell")
        if not manager.booleanOperation(replacement, pocket, adsk.fusion.BooleanTypes.DifferenceBooleanType):
            raise RuntimeError("The concealed ESP32 relief did not intersect the shell")

        for body in component.bRepBodies:
            if body != source:
                body.isVisible = False
        source.isVisible = False
        corrected = _add_body(component, replacement, "Dock + Rear USB-C Opening and ESP32 Relief v3")
        corrected.isVisible = True

        _parameter(design, "Dock_USBC_Opening_Width", "12 mm", "mm", "Final physical-rear USB-C cable opening")
        _parameter(design, "Dock_USBC_Opening_Height", "7 mm", "mm", "Final physical-rear USB-C cable opening")
        _parameter(design, "Dock_USBC_Corner_Radius", "1 mm", "mm", "Final USB-C opening corner radius")
        _parameter(design, "Dock_ESP32_Rear_Relief_Width", "18.8 mm", "mm", "Hidden relief for ESP32 module PCB")
        _parameter(design, "Dock_ESP32_Rear_Skin", "0.8 mm", "mm", "Rear skin retained outside hidden ESP32 relief")

        report = {
            "document_before_save": app.activeDocument.name,
            "physical_rear": "Fusion Z=-70 mm",
            "body": corrected.name,
            "opening_mm": {
                "centre_x": CENTRE_X_MM, "centre_y": CENTRE_Y_MM,
                "width": WIDTH_MM, "height": HEIGHT_MM, "corner_radius": CORNER_RADIUS_MM,
            },
            "hidden_relief_mm": {
                "centre_x": POCKET_X_MM, "centre_y": POCKET_Y_MM,
                "width": POCKET_WIDTH_MM, "height": POCKET_HEIGHT_MM,
                "z_min": POCKET_Z_MIN_MM, "z_max": POCKET_Z_MAX_MM,
                "retained_outer_skin": 0.8,
            },
            "corrected_bbox": _bbox_mm(corrected.boundingBox),
            "corrected_volume_cm3": corrected.volume,
        }
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        app.activeDocument.save("Final rear USB-C and concealed ESP32 wall relief")
        print("Rear USB-C fit v3 created and saved: 12 x 7 mm opening, hidden 18.8 mm ESP32 relief, 0.8 mm exterior skin")
    except Exception:
        print("Dock rear USB-C fit v3 failed:\n" + traceback.format_exc())
