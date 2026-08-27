"""Replace the imported Dock Rev6 PCB with a fresh KiCad STEP export.

The old board model (`Dock Rev6 PCB - Bottom ESP32 Headers`, or any earlier
`Dock Rev6 PCB*` import) is deleted and `Dock Rev6 PCB Assembly.step` is
imported in its place, then checked for solid interference against the dock
shell and the base lid.

The STEP is exported by kicad-cli in absolute board coordinates, so the
placement transform is unchanged from the earlier mechanical check:

    dock X = step X - 100 mm
    dock Y = step Z + 8 mm       (PCB seating plane on the lid bosses)
    dock Z = -step Y - 140 mm    (owner-confirmed mirrored physical face)
"""

import adsk.core
import adsk.fusion
import json
import math
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
STEP_PATH = os.path.join(WORKSPACE, "PCB", "Dock Rev6", "Dock Rev6 PCB Assembly.step")
REPORT_PATH = os.path.join(
    WORKSPACE, "CAD", "Dock Rev6", "Charging Dock Rev6 PCB Replace Report.json"
)

# Every previous import used a component name starting with this prefix:
# "Dock Rev6 PCB Mechanical Check", "Dock Rev6 PCB - Bottom ESP32 Headers".
OLD_NAME_PREFIX = "Dock Rev6 PCB"
NEW_NAME = "Dock Rev6 PCB"

DOCK_PATH = "Dock:1"
LID_PATH = "Dock Base Lid:1"

# Body names are tried in order; the first match wins, otherwise every visible
# solid in the occurrence is used.
DOCK_BODY_NAMES = [
    "Dock - User Editable Shell (No Cutouts)",
    "Dock + Correct Rear USB-C Opening",
    "Dock",
]
LID_BODY_NAMES = [
    "Dock Base Lid + PCB Bosses",
    "Body6",
    "Dock Base Lid",
]

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


def _target_solids(occurrence, preferred_names):
    """Return the assembly-context solids to test this occurrence against."""
    for name in preferred_names:
        body = occurrence.component.bRepBodies.itemByName(name)
        if body:
            return [(name, body.createForAssemblyContext(occurrence))]
    found = [(b.name, b) for b in occurrence.bRepBodies if b.isVisible and b.isSolid]
    if not found:
        raise RuntimeError("No visible solid found in " + occurrence.fullPathName)
    return found


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
    ok = manager.booleanOperation(
        first, second, adsk.fusion.BooleanTypes.IntersectionBooleanType
    )
    if not ok:
        return 0.0, None
    return first.volume, _bbox_mm(first.boundingBox)


def _write_report(payload):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def run(context):
    try:
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        if not os.path.isfile(STEP_PATH):
            raise RuntimeError("KiCad STEP export not found: " + STEP_PATH)

        root = design.rootComponent
        document_name = app.activeDocument.name

        # 1. Remove the previous board import.  Abort rather than leave two
        # overlapping PCBs in the assembly if nothing matches.
        stale = [
            occurrence for occurrence in root.occurrences
            if occurrence.component.name.startswith(OLD_NAME_PREFIX)
        ]
        if not stale:
            existing = [o.component.name for o in root.occurrences]
            _write_report({
                "status": "aborted",
                "document": document_name,
                "reason": (
                    "No root occurrence starts with '{}'; nothing was imported so "
                    "the assembly cannot end up with two boards.".format(OLD_NAME_PREFIX)
                ),
                "root_occurrences": existing,
            })
            print("Aborted: no existing '{}*' occurrence found.".format(OLD_NAME_PREFIX))
            print("Root occurrences: " + ", ".join(existing))
            print("Report: " + REPORT_PATH)
            return

        removed = [occurrence.component.name for occurrence in stale]
        for occurrence in stale:
            occurrence.deleteMe()

        # 2. Import the fresh export at the confirmed placement.
        transform = adsk.core.Matrix3D.create()
        transform.setToRotation(
            -math.pi / 2.0,
            adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Point3D.create(0, 0, 0),
        )
        transform.translation = adsk.core.Vector3D.create(-10.0, 0.8, -14.0)

        pcb_occurrence = root.occurrences.addNewComponent(transform)
        component = pcb_occurrence.component
        component.name = NEW_NAME
        component.partNumber = NEW_NAME
        component.description = "kicad-cli STEP export of PCB/Dock Rev6/Dock Rev6.kicad_pcb"
        importer = app.importManager
        options = importer.createSTEPImportOptions(STEP_PATH)
        if not importer.importToTarget(options, component):
            raise RuntimeError("Fusion failed to import " + STEP_PATH)
        pcb_occurrence.isLightBulbOn = True

        # 3. Interference check.  Dock-shell hits are expected wherever the
        # owner has not cut the USB / button / LED apertures yet; a base-lid
        # hit means the underside ESP32 assembly no longer fits.
        dock_occurrence = _find_occurrence(root, DOCK_PATH)
        lid_occurrence = _find_occurrence(root, LID_PATH)
        targets = []
        for label, occurrence, names in (
            ("dock_shell", dock_occurrence, DOCK_BODY_NAMES),
            ("base_lid", lid_occurrence, LID_BODY_NAMES),
        ):
            for body_name, body in _target_solids(occurrence, names):
                targets.append((label, body_name, body))

        manager = adsk.fusion.TemporaryBRepManager.get()
        bodies = _pcb_bodies(root, pcb_occurrence)
        collisions = []
        for path, body in bodies:
            for label, body_name, target in targets:
                volume, intersection_bbox = _intersection(manager, body, target)
                if volume > VOLUME_TOLERANCE_CM3:
                    collisions.append({
                        "pcb_path": path,
                        "pcb_body": body.name,
                        "target": label,
                        "target_body": body_name,
                        "intersection_cm3": volume,
                        "pcb_bbox": _bbox_mm(body.boundingBox),
                        "intersection_bbox": intersection_bbox,
                    })

        lid_hits = [c for c in collisions if c["target"] == "base_lid"]
        shell_hits = [c for c in collisions if c["target"] == "dock_shell"]
        payload = {
            "status": "imported",
            "document_before_save": document_name,
            "step_path": STEP_PATH,
            "removed_components": removed,
            "component": NEW_NAME,
            "transform": {
                "dock_x": "step_x - 100 mm",
                "dock_y": "step_z + 8 mm",
                "dock_z": "-step_y - 140 mm",
            },
            "checked_targets": [
                {"target": label, "body": body_name} for label, body_name, _ in targets
            ],
            "pcb_solid_count": len(bodies),
            "collision_volume_tolerance_cm3": VOLUME_TOLERANCE_CM3,
            "base_lid_collision_count": len(lid_hits),
            "dock_shell_collision_count": len(shell_hits),
            "collisions": collisions,
        }
        _write_report(payload)

        app.activeDocument.save(
            "Replaced the Dock Rev6 PCB with the current KiCad STEP export"
        )
        print("Removed: " + ", ".join(removed))
        print("Imported '{}' ({} solids) from {}".format(NEW_NAME, len(bodies), STEP_PATH))
        if lid_hits:
            print("FAIL: {} base-lid interference(s) — the board no longer clears the "
                  "lid or its bosses.".format(len(lid_hits)))
        else:
            print("PASS: no base-lid interference.")
        print("{} dock-shell interference(s) (expected until the USB / button / LED "
              "apertures are cut).".format(len(shell_hits)))
        print("Report: " + REPORT_PATH)
    except Exception:
        print("Dock Rev6 PCB replacement failed:\n" + traceback.format_exc())
