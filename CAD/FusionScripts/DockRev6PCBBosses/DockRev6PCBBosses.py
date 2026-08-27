import adsk.core
import adsk.fusion
import json
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
REPORT_PATH = os.path.join(
    WORKSPACE, "CAD", "Dock Rev6", "Charging Dock Rev6 PCB Boss Report.json"
)

# Fusion API length values are centimetres. These centres match the KiCad
# mechanical board exactly in the dock's X/Z coordinate system.
CENTRES_MM = [
    (+18.5, +6.0),
    (-18.5, +6.0),
    (+18.5, -46.0),
    (-18.5, -46.0),
]
BOSS_OD_MM = 7.5
BOSS_BASE_Y_MM = 1.0
BOSS_TOP_Y_MM = 8.0
PILOT_DIAMETER_MM = 2.55
PILOT_BOTTOM_Y_MM = 4.0
PILOT_TOP_Y_MM = 8.1
MARKER = "Dock_PCB_Boss_Version"


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
    return design.userParameters.add(
        name, adsk.core.ValueInput.createByString(expression), units, comment
    )


def _find_lid(root):
    for occurrence in root.allOccurrences:
        if occurrence.fullPathName == "Dock Base Lid:1":
            if occurrence.isReferencedComponent:
                raise RuntimeError("Dock Base Lid is externally referenced and cannot be edited.")
            body = occurrence.component.bRepBodies.itemByName("Dock Base Lid")
            if not body:
                raise RuntimeError("Dock Base Lid body was not found in its component.")
            return occurrence, occurrence.component, body
    raise RuntimeError("The top-level Dock Base Lid:1 occurrence was not found.")


def _make_boss(manager, x_mm, z_mm):
    boss = manager.createCylinderOrCone(
        _point_mm(x_mm, BOSS_BASE_Y_MM, z_mm),
        BOSS_OD_MM / 20.0,
        _point_mm(x_mm, BOSS_TOP_Y_MM, z_mm),
        BOSS_OD_MM / 20.0,
    )
    pilot = manager.createCylinderOrCone(
        _point_mm(x_mm, PILOT_BOTTOM_Y_MM, z_mm),
        PILOT_DIAMETER_MM / 20.0,
        _point_mm(x_mm, PILOT_TOP_Y_MM, z_mm),
        PILOT_DIAMETER_MM / 20.0,
    )
    ok = manager.booleanOperation(
        boss, pilot, adsk.fusion.BooleanTypes.DifferenceBooleanType
    )
    if not ok:
        raise RuntimeError("Could not cut a blind pilot hole in a PCB boss.")
    return boss


def _add_temp_body(component, body, name):
    base = component.features.baseFeatures.add()
    base.name = name + " Base Feature"
    base.startEdit()
    added = component.bRepBodies.add(body, base)
    base.finishEdit()
    added.name = name
    return added


def _direct_model_replacement(manager, component, target, bosses):
    """Union bosses into a temporary copy, preserving the source as rollback."""
    replacement = manager.copy(target)
    if not replacement:
        raise RuntimeError("Could not copy the Dock Base Lid BRep.")
    for index, boss in enumerate(bosses, 1):
        ok = manager.booleanOperation(
            replacement, boss, adsk.fusion.BooleanTypes.UnionBooleanType
        )
        if not ok:
            raise RuntimeError("Direct BRep union failed for PCB boss {}.".format(index))
    added = _add_temp_body(component, replacement, "Dock Base Lid + PCB Bosses")
    target.name = "Dock Base Lid Pre-PCB-Boss Backup"
    target.isVisible = False
    added.isVisible = True
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
            raise RuntimeError(
                "The PCB-boss marker already exists. This script is intentionally idempotent."
            )

        root = design.rootComponent
        occurrence, component, lid = _find_lid(root)
        before = {
            "name": lid.name,
            "volume_cm3": lid.volume,
            "face_count": lid.faces.count,
            "bbox": _bbox_mm(lid.boundingBox),
        }

        manager = adsk.fusion.TemporaryBRepManager.get()
        temp_bosses = [_make_boss(manager, x, z) for x, z in CENTRES_MM]
        lid = _direct_model_replacement(manager, component, lid, temp_bosses)

        _parameter(design, "Dock_PCB_Boss_OD", "7.5 mm", "mm", "PCB boss outside diameter")
        _parameter(design, "Dock_PCB_Boss_Top_Y", "8 mm", "mm", "PCB seating plane above dock origin")
        _parameter(design, "Dock_PCB_Boss_Pilot_Diameter", "2.55 mm", "mm", "M3 thread-forming pilot")
        _parameter(design, "Dock_PCB_Boss_Thread_Engagement", "3.4 mm", "mm", "M3x5 engagement below a 1.6 mm PCB")
        _parameter(design, MARKER, "1", "", "Dock Rev6 four-boss feature marker")

        after = {
            "name": lid.name,
            "volume_cm3": lid.volume,
            "face_count": lid.faces.count,
            "bbox": _bbox_mm(lid.boundingBox),
        }
        report = {
            "document": app.activeDocument.name,
            "occurrence": occurrence.fullPathName,
            "component": component.name,
            "centres_mm": [{"x": x, "y": BOSS_TOP_Y_MM, "z": z} for x, z in CENTRES_MM],
            "boss_od_mm": BOSS_OD_MM,
            "pilot_diameter_mm": PILOT_DIAMETER_MM,
            "pilot_depth_mm": PILOT_TOP_Y_MM - PILOT_BOTTOM_Y_MM,
            "pcb_thickness_mm": 1.6,
            "screw_spec": "4x M3x5 mm",
            "thread_engagement_mm": 3.4,
            "before": before,
            "after": after,
        }
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        ui.messageBox(
            "Added four blind M3 PCB bosses to Dock Base Lid.\n\n"
            "Pattern: 37 x 52 mm\nBoss OD: 7.5 mm\nPilot: 2.55 mm\n"
            "Seat Y: 8.0 mm for a 1.6 mm PCB and M3x5 screws."
        )
    except Exception:
        if ui:
            ui.messageBox("Dock PCB boss creation failed:\n" + traceback.format_exc())
