import adsk.core
import adsk.fusion
import json
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
REPORT_PATH = os.path.join(WORKSPACE, "CAD", "Dock Rev6", "Charging Dock Rev6 Rear USB-C Report.json")

# Derived from the KiCad STEP with U1 at (99.87, 80.89).  Fusion uses the
# dock's X/Y/Z coordinate system directly.  Dimensions include approximately
# 1.1 mm lateral and 1.0 mm vertical clearance around the metal receptacle.
CENTRE_X_MM = -0.43
CENTRE_Y_MM = 11.73
WIDTH_MM = 11.2
HEIGHT_MM = 6.0
CORNER_RADIUS_MM = 1.5
Z_MIN_MM = 26.0
Z_MAX_MM = 35.0
MARKER = "Dock_Rear_USBC_Opening_Version"


def _point_mm(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def _bbox_mm(box):
    return {
        "min_mm": [box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10],
        "max_mm": [box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10],
    }


def _parameter(design, name, expression, units, comment):
    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        existing.comment = comment
        return existing
    return design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), units, comment)


def _find_dock(root):
    for occurrence in root.occurrences:
        if occurrence.fullPathName == "Dock:1":
            if occurrence.isReferencedComponent:
                raise RuntimeError("Dock:1 is externally referenced and cannot be edited.")
            body = occurrence.component.bRepBodies.itemByName("Dock")
            if not body:
                # Permit reruns during development before the marker is saved.
                for candidate in occurrence.component.bRepBodies:
                    if candidate.isVisible and candidate.isSolid:
                        body = candidate
                        break
            if not body:
                raise RuntimeError("The editable Dock shell body was not found.")
            return occurrence, occurrence.component, body
    raise RuntimeError("The top-level Dock:1 occurrence was not found.")


def _box(manager, length_mm, width_mm, depth_mm):
    centre = _point_mm(CENTRE_X_MM, CENTRE_Y_MM, (Z_MIN_MM + Z_MAX_MM) / 2.0)
    obb = adsk.core.OrientedBoundingBox3D.create(
        centre,
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0),
        length_mm / 10.0,
        width_mm / 10.0,
        depth_mm / 10.0,
    )
    return manager.createBox(obb)


def _rounded_cutter(manager):
    depth = Z_MAX_MM - Z_MIN_MM
    radius = CORNER_RADIUS_MM
    cutter = _box(manager, WIDTH_MM - 2 * radius, HEIGHT_MM, depth)
    vertical = _box(manager, WIDTH_MM, HEIGHT_MM - 2 * radius, depth)
    if not manager.booleanOperation(cutter, vertical, adsk.fusion.BooleanTypes.UnionBooleanType):
        raise RuntimeError("Could not build the rounded USB-C cutter cross-section.")

    dx = WIDTH_MM / 2.0 - radius
    dy = HEIGHT_MM / 2.0 - radius
    for x_sign in (-1, 1):
        for y_sign in (-1, 1):
            x = CENTRE_X_MM + x_sign * dx
            y = CENTRE_Y_MM + y_sign * dy
            cylinder = manager.createCylinderOrCone(
                _point_mm(x, y, Z_MIN_MM),
                radius / 10.0,
                _point_mm(x, y, Z_MAX_MM),
                radius / 10.0,
            )
            if not manager.booleanOperation(cutter, cylinder, adsk.fusion.BooleanTypes.UnionBooleanType):
                raise RuntimeError("Could not round a USB-C cutter corner.")
    return cutter


def _add_temp_body(component, body, name):
    base = component.features.baseFeatures.add()
    base.name = name + " Base Feature"
    base.startEdit()
    added = component.bRepBodies.add(body, base)
    base.finishEdit()
    added.name = name
    return added


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        if design.userParameters.itemByName(MARKER):
            raise RuntimeError("The rear USB-C opening already exists in this design.")

        occurrence, component, target = _find_dock(design.rootComponent)
        before = {
            "name": target.name,
            "volume_cm3": target.volume,
            "face_count": target.faces.count,
            "bbox": _bbox_mm(target.boundingBox),
        }
        manager = adsk.fusion.TemporaryBRepManager.get()
        replacement = manager.copy(target)
        cutter = _rounded_cutter(manager)
        if not manager.booleanOperation(replacement, cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType):
            raise RuntimeError("The rounded USB-C cutter did not intersect the dock shell.")

        added = _add_temp_body(component, replacement, "Dock + Rear USB-C Opening")
        target.name = "Dock Pre-Rear-USB-C Backup"
        target.isVisible = False
        added.isVisible = True

        _parameter(design, "Dock_USBC_Centre_X", "-0.43 mm", "mm", "Rear USB-C opening centre from KiCad U1")
        _parameter(design, "Dock_USBC_Centre_Y", "11.73 mm", "mm", "Rear USB-C opening height from PCB seat")
        _parameter(design, "Dock_USBC_Opening_Width", "11.2 mm", "mm", "Rounded rear USB-C access width")
        _parameter(design, "Dock_USBC_Opening_Height", "6.0 mm", "mm", "Rounded rear USB-C access height")
        _parameter(design, "Dock_USBC_Corner_Radius", "1.5 mm", "mm", "Rear USB-C opening corner radius")
        _parameter(design, MARKER, "1", "", "Dock Rev6 rear USB-C opening marker")

        after = {
            "name": added.name,
            "volume_cm3": added.volume,
            "face_count": added.faces.count,
            "bbox": _bbox_mm(added.boundingBox),
        }
        if after["volume_cm3"] >= before["volume_cm3"]:
            raise RuntimeError("USB-C opening verification failed: shell volume did not decrease.")

        report = {
            "document": app.activeDocument.name,
            "occurrence": occurrence.fullPathName,
            "opening_mm": {
                "centre_x": CENTRE_X_MM,
                "centre_y": CENTRE_Y_MM,
                "width": WIDTH_MM,
                "height": HEIGHT_MM,
                "corner_radius": CORNER_RADIUS_MM,
                "z_min": Z_MIN_MM,
                "z_max": Z_MAX_MM,
            },
            "before": before,
            "after": after,
            "removed_volume_cm3": before["volume_cm3"] - after["volume_cm3"],
        }
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        app.activeDocument.save("Rear USB-C opening aligned to Dock Rev6 ESP32-C3 PCB")
        ui.messageBox(
            "Rear USB-C opening created and saved.\n\n"
            "11.2 x 6.0 mm, R1.5\n"
            "Centre X=-0.43 mm, Y=11.73 mm"
        )
    except Exception:
        if ui:
            ui.messageBox("Dock rear USB-C opening failed:\n" + traceback.format_exc())
