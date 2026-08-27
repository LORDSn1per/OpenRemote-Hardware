import adsk.core
import adsk.fusion
import json
import math
import os
import traceback


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_reset_hole_report.json",
)

# Rev6 S26 is the rear-facing TL3342 switch on ESP_EN. KiCad places its
# footprint origin at (63.15 mm, 120.625 mm). The imported STEP uses -Y.
S26_STEP_X_CM = 6.315
S26_STEP_Y_CM = -12.0625
HOLE_RADIUS_CM = 0.11


def _point(point):
    return [point.x, point.y, point.z]


def _bbox(box):
    return {"min_cm": _point(box.minPoint), "max_cm": _point(box.maxPoint)}


def _find_rev6_board(root):
    matches = [
        occurrence
        for occurrence in root.allOccurrences
        if occurrence.component.name == "OpenRemote_PCB"
        and "OpenRemote PCB Rev6" in occurrence.fullPathName
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one imported Rev6 bare-board occurrence; found {}.".format(
                len(matches)
            )
        )
    return matches[0]


def _find_s26(root, expected_root):
    candidates = []
    for occurrence in root.allOccurrences:
        if "OpenRemote PCB Rev6" not in occurrence.fullPathName:
            continue
        if not occurrence.component.name.startswith("SW_SPST_TL3342 (1)"):
            continue
        matrix = occurrence.transform2
        x = matrix.getCell(0, 3)
        y = matrix.getCell(1, 3)
        distance = math.hypot(x - expected_root.x, y - expected_root.y)
        candidates.append((distance, occurrence, x, y))
    if not candidates:
        raise RuntimeError("No Rev6 TL3342 switch occurrences were found.")
    candidates.sort(key=lambda item: item[0])
    distance, occurrence, x, y = candidates[0]
    if distance > 0.001:
        raise RuntimeError(
            "Nearest TL3342 is {:.3f} mm from the S26 KiCad position.".format(
                distance * 10
            )
        )
    return occurrence, distance, x, y


def _parameter(design):
    existing = design.userParameters.itemByName("Reset_Access_Hole_Diameter")
    if existing:
        existing.expression = "2.2 mm"
        existing.comment = "Rear-case pin access aligned to Rev6 reset switch S26."
        return existing
    return design.userParameters.add(
        "Reset_Access_Hole_Diameter",
        adsk.core.ValueInput.createByString("2.2 mm"),
        "mm",
        "Rear-case pin access aligned to Rev6 reset switch S26.",
    )


def _cut_hole(root, case, x, y):
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByString("-30 mm"),
    )
    plane = root.constructionPlanes.add(plane_input)
    plane.name = "Rev6 Reset Access Plane"
    plane.isLightBulbOn = False

    sketch = root.sketches.add(plane)
    sketch.name = "Rev6 Reset Access Hole Sketch"
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(x, y, 0),
        HOLE_RADIUS_CM,
    )
    if sketch.profiles.count != 1:
        raise RuntimeError(
            "Expected one reset-hole profile; found {}.".format(
                sketch.profiles.count
            )
        )
    sketch.isLightBulbOn = False

    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    extrude_input.participantBodies = [case]
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByString("35 mm")
    )
    extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    feature = extrudes.add(extrude_input)
    feature.name = "Rev6 Reset Access Hole"
    return feature


def _matching_case_cylinders(case, x, y):
    matches = []
    for face in case.faces:
        cylinder = adsk.core.Cylinder.cast(face.geometry)
        if not cylinder:
            continue
        if (
            abs(cylinder.radius - HOLE_RADIUS_CM) < 1e-5
            and abs(cylinder.origin.x - x) < 1e-4
            and abs(cylinder.origin.y - y) < 1e-4
        ):
            matches.append(
                {
                    "radius_cm": cylinder.radius,
                    "origin_cm": _point(cylinder.origin),
                    "bbox_root": _bbox(face.boundingBox),
                }
            )
    return matches


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        if not app.activeDocument.name.startswith("OpenRemote Hardware Rev6"):
            raise RuntimeError(
                "Open the OpenRemote Hardware Rev6 root assembly before running this script."
            )

        root = design.rootComponent
        if root.features.itemByName("Rev6 Reset Access Hole"):
            raise RuntimeError("The Rev6 reset access hole already exists.")

        board = _find_rev6_board(root)
        expected_root = adsk.core.Point3D.create(
            S26_STEP_X_CM,
            S26_STEP_Y_CM,
            0,
        )
        expected_root.transformBy(board.transform2)
        switch, switch_delta, switch_x, switch_y = _find_s26(root, expected_root)
        # Capture the imported switch envelope before recomputing the root
        # design; Fusion can invalidate an occurrence bounding-box proxy after
        # a root-body feature is added.
        switch_box = switch.boundingBox
        switch_bbox_values = _bbox(switch_box)
        switch_center_values = [
            (switch_box.minPoint.x + switch_box.maxPoint.x) / 2,
            (switch_box.minPoint.y + switch_box.maxPoint.y) / 2,
            (switch_box.minPoint.z + switch_box.maxPoint.z) / 2,
        ]

        case = root.bRepBodies.itemByName("Case")
        if not case:
            raise RuntimeError("The root rear Case body was not found.")
        _parameter(design)
        feature = _cut_hole(root, case, switch_x, switch_y)
        design.computeAll()

        cylinders = _matching_case_cylinders(case, switch_x, switch_y)
        if not cylinders:
            raise RuntimeError(
                "The case cut completed but its 2.2 mm cylindrical face could not be verified."
            )

        axis_samples = []
        for z_mm in range(-30, 6):
            containment = int(
                case.pointContainment(
                    adsk.core.Point3D.create(switch_x, switch_y, z_mm / 10.0)
                )
            )
            axis_samples.append({"z_mm": z_mm, "containment": containment})
        if any(sample["containment"] == 0 for sample in axis_samples):
            raise RuntimeError("Solid rear-case material remains on the reset axis.")

        report = {
            "document": app.activeDocument.name,
            "source": {
                "reference": "S26",
                "function": "ESP32 EN/reset",
                "part": "TL3342F160QG",
                "kicad_xy_mm": [63.15, 120.625],
                "step_xy_cm": [S26_STEP_X_CM, S26_STEP_Y_CM],
            },
            "expected_axis_root_cm": _point(expected_root),
            "matched_switch_occurrence": switch.fullPathName,
            "matched_switch_origin_root_cm": [switch_x, switch_y],
            "matched_switch_center_root_cm": switch_center_values,
            "matched_switch_bbox_root": switch_bbox_values,
            "source_to_switch_axis_delta_mm": switch_delta * 10,
            "hole_diameter_mm": 2.2,
            "case_feature": feature.name,
            "verified_case_cylinders": cylinders,
            "case_axis_samples": axis_samples,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Rev6 reset access created.\n\n"
            "A verified 2.2 mm hole now passes through the rear Case on the "
            "exact center axis of the imported Rev6 S26 reset switch."
        )
    except Exception:
        if ui:
            ui.messageBox("Rev6 reset-hole update failed:\n" + traceback.format_exc())
