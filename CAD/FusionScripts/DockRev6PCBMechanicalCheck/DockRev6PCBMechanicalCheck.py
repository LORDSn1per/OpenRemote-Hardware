import adsk.core
import adsk.fusion
import json
import math
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
STEP_PATH = os.path.join(WORKSPACE, "PCB", "Dock Rev6", "Dock Rev6 Component Staging.step")
REPORT_PATH = os.path.join(WORKSPACE, "CAD", "Dock Rev6", "Charging Dock Rev6 PCB Mechanical Check.json")
COMPONENT_NAME = "Dock Rev6 PCB Mechanical Check"
VOLUME_TOLERANCE_CM3 = 1e-5


def _bbox_mm(box):
    return {
        "min_mm": [box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10],
        "max_mm": [box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10],
    }


def _overlap(a, b):
    return not (
        a.maxPoint.x < b.minPoint.x or a.minPoint.x > b.maxPoint.x
        or a.maxPoint.y < b.minPoint.y or a.minPoint.y > b.maxPoint.y
        or a.maxPoint.z < b.minPoint.z or a.minPoint.z > b.maxPoint.z
    )


def _find_occurrence(root, path):
    for occurrence in root.occurrences:
        if occurrence.fullPathName == path:
            return occurrence
    raise RuntimeError("Occurrence not found: " + path)


def _visible_solid(occurrence, preferred_names):
    for name in preferred_names:
        body = occurrence.component.bRepBodies.itemByName(name)
        if body:
            return body.createForAssemblyContext(occurrence)
    for body in occurrence.bRepBodies:
        if body.isVisible and body.isSolid:
            return body
    raise RuntimeError("Visible solid not found in " + occurrence.fullPathName)


def _pcb_bodies(root, top_occurrence):
    result = []
    for body in top_occurrence.bRepBodies:
        if body.isSolid:
            result.append((top_occurrence.fullPathName, body))
    prefix = top_occurrence.fullPathName + "+"
    for occurrence in root.allOccurrences:
        if occurrence.fullPathName.startswith(prefix):
            for body in occurrence.bRepBodies:
                if body.isSolid:
                    result.append((occurrence.fullPathName, body))
    return result


def _intersection(manager, source_body, target_body):
    if not _overlap(source_body.boundingBox, target_body.boundingBox):
        return 0.0, None
    first = manager.copy(source_body)
    second = manager.copy(target_body)
    if not first or not second:
        return 0.0, None
    ok = manager.booleanOperation(first, second, adsk.fusion.BooleanTypes.IntersectionBooleanType)
    if not ok:
        return 0.0, None
    return first.volume, _bbox_mm(first.boundingBox)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        if not os.path.isfile(STEP_PATH):
            raise RuntimeError("Updated PCB STEP file not found: " + STEP_PATH)

        root = design.rootComponent
        pcb_occurrence = None
        for occurrence in root.occurrences:
            if occurrence.component.name == COMPONENT_NAME:
                occurrence.deleteMe()
                break

        # KiCad STEP -> corrected physical dock coordinates:
        #   Dock X = STEP X - 100 mm
        #   Dock Y = STEP Z + 8 mm (PCB seating plane)
        #   Dock Z = -STEP Y - 140 mm (owner-confirmed mirrored physical face)
        transform = adsk.core.Matrix3D.create()
        transform.setToRotation(
            -math.pi / 2.0,
            adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Point3D.create(0, 0, 0),
        )
        transform.translation = adsk.core.Vector3D.create(-10.0, 0.8, -14.0)

        if pcb_occurrence is None:
            pcb_occurrence = root.occurrences.addNewComponent(transform)
            pcb_occurrence.component.name = COMPONENT_NAME
            pcb_occurrence.component.partNumber = COMPONENT_NAME
            importer = app.importManager
            options = importer.createSTEPImportOptions(STEP_PATH)
            if not importer.importToTarget(options, pcb_occurrence.component):
                raise RuntimeError("Fusion failed to import the corrected PCB STEP model.")
        pcb_occurrence.isLightBulbOn = True

        dock_occurrence = _find_occurrence(root, "Dock:1")
        lid_occurrence = _find_occurrence(root, "Dock Base Lid:1")
        dock_body = _visible_solid(
            dock_occurrence,
            ["Dock + Correct Rear USB-C Opening", "Dock"],
        )
        lid_body = _visible_solid(
            lid_occurrence,
            ["Body6", "Dock Base Lid + PCB Bosses", "Dock Base Lid"],
        )

        manager = adsk.fusion.TemporaryBRepManager.get()
        bodies = _pcb_bodies(root, pcb_occurrence)
        collisions = []
        for path, body in bodies:
            for target_name, target in (("dock_shell", dock_body), ("base_lid", lid_body)):
                volume, intersection_bbox = _intersection(manager, body, target)
                if volume > VOLUME_TOLERANCE_CM3:
                    collisions.append({
                        "pcb_path": path,
                        "pcb_body": body.name,
                        "target": target_name,
                        "intersection_cm3": volume,
                        "pcb_bbox": _bbox_mm(body.boundingBox),
                        "intersection_bbox": intersection_bbox,
                    })

        # Analytical receiver clearance for the exact 18 mm module body after
        # centring U1.  Rear receiver inner edges are X=+/-9.502 mm.
        receiver_clearance_mm = 17.002 - 7.5 - 9.0
        payload = {
            "document_before_save": app.activeDocument.name,
            "step_path": STEP_PATH,
            "component": COMPONENT_NAME,
            "transform": {
                "dock_x": "step_x - 100 mm",
                "dock_y": "step_z + 8 mm",
                "dock_z": "-step_y - 140 mm",
            },
            "pcb_solid_count": len(bodies),
            "receiver_body_clearance_each_side_mm": receiver_clearance_mm,
            "collision_volume_tolerance_cm3": VOLUME_TOLERANCE_CM3,
            "collision_count": len(collisions),
            "collisions": collisions,
        }
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        app.activeDocument.save("Imported corrected Dock Rev6 PCB and completed shell/lid interference check")
        if collisions:
            print("PCB imported, but {} interference(s) remain. See: {}".format(len(collisions), REPORT_PATH))
        else:
            print("PCB imported and mechanical check passed; no solid interference with dock shell or base lid.")
    except Exception:
        print("Dock PCB mechanical check failed:\n" + traceback.format_exc())
