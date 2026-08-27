import adsk.core
import adsk.fusion
import json
import math
import os
import traceback


STEP_PATH = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware/CAD/PCB Imports/OpenRemote Rev6 PCB.step"
REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_pcb_and_mic_hole_report.json",
)

# The Rev6 MIC1 footprint is at (142.5 mm, 102.0 mm). KiCad's STEP exporter
# uses a negative Y coordinate, so the acoustic-hole axis is (14.25, -10.2)
# centimetres in the exported STEP coordinate system.
MIC_STEP_X_CM = 14.25
MIC_STEP_Y_CM = -10.2
MIC_HOLE_RADIUS_CM = 0.10


def _matrix_values(matrix):
    return [matrix.getCell(row, col) for row in range(4) for col in range(4)]


def _point_values(point):
    return [point.x, point.y, point.z]


def _bbox_values(box):
    return {
        "min_cm": _point_values(box.minPoint),
        "max_cm": _point_values(box.maxPoint),
    }


def _find_old_board(root):
    candidates = []
    for occurrence in root.allOccurrences:
        if (
            occurrence.component.name == "Remote PCB"
            and "OMOTE Rev2" in occurrence.fullPathName
        ):
            candidates.append(occurrence)
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one OMOTE Rev2 Remote PCB occurrence; found {}.".format(
                len(candidates)
            )
        )
    return candidates[0]


def _find_old_top_occurrence(root):
    candidates = [
        occurrence
        for occurrence in root.occurrences
        if "OMOTE Rev2" in occurrence.name
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one top-level OMOTE Rev2 occurrence; found {}.".format(
                len(candidates)
            )
        )
    return candidates[0]


def _parameter(design, name, expression, units, comment):
    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        existing.comment = comment
        return existing
    return design.userParameters.add(
        name,
        adsk.core.ValueInput.createByString(expression),
        units,
        comment,
    )


def _cut_mic_hole(root, cover, mic_root):
    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByString("-5 mm"),
    )
    plane = planes.add(plane_input)
    plane.name = "Rev6 Microphone Opening Plane"
    plane.isLightBulbOn = False

    sketch = root.sketches.add(plane)
    sketch.name = "Rev6 Microphone Acoustic Opening Sketch"
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mic_root.x, mic_root.y, 0),
        MIC_HOLE_RADIUS_CM,
    )
    if sketch.profiles.count != 1:
        raise RuntimeError(
            "Expected one microphone-hole profile; found {}.".format(
                sketch.profiles.count
            )
        )
    sketch.isLightBulbOn = False

    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    extrude_input.participantBodies = [cover]
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByString("10 mm")
    )
    extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    feature = extrudes.add(extrude_input)
    feature.name = "Rev6 Microphone Acoustic Opening"
    return feature


def _matching_cover_cylinders(cover, mic_root):
    matches = []
    for face in cover.faces:
        cylinder = adsk.core.Cylinder.cast(face.geometry)
        if not cylinder:
            continue
        if (
            abs(cylinder.radius - MIC_HOLE_RADIUS_CM) < 1e-5
            and abs(cylinder.origin.x - mic_root.x) < 1e-4
            and abs(cylinder.origin.y - mic_root.y) < 1e-4
        ):
            matches.append(
                {
                    "radius_cm": cylinder.radius,
                    "origin_cm": _point_values(cylinder.origin),
                    "bbox": _bbox_values(face.boundingBox),
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
        if not os.path.isfile(STEP_PATH):
            raise RuntimeError("Rev6 PCB STEP file not found: " + STEP_PATH)

        root = design.rootComponent
        if root.features.itemByName("Rev6 Microphone Acoustic Opening"):
            raise RuntimeError("The Rev6 PCB and microphone opening already exist.")
        if any(
            occurrence.component.name == "OpenRemote PCB Rev6"
            for occurrence in root.occurrences
        ):
            raise RuntimeError("An OpenRemote PCB Rev6 component already exists.")

        old_board = _find_old_board(root)
        old_top = _find_old_top_occurrence(root)
        exact_transform = old_board.transform2.copy()

        new_occurrence = root.occurrences.addNewComponent(exact_transform)
        new_occurrence.component.name = "OpenRemote PCB Rev6"
        new_occurrence.component.partNumber = "OpenRemote PCB Rev6"

        importer = app.importManager
        step_options = importer.createSTEPImportOptions(STEP_PATH)
        if not importer.importToTarget(step_options, new_occurrence.component):
            raise RuntimeError("Fusion failed to import the Rev6 PCB STEP model.")

        # Retain the old linked component but hide it so the two complete PCB
        # assemblies do not visually overlap. Its browser eyeball remains usable.
        old_top.isLightBulbOn = False
        new_occurrence.isLightBulbOn = True

        mic_local = adsk.core.Point3D.create(
            MIC_STEP_X_CM,
            MIC_STEP_Y_CM,
            0,
        )
        mic_root = mic_local.copy()
        mic_root.transformBy(exact_transform)

        _parameter(
            design,
            "Mic_Acoustic_Opening_Diameter",
            "2.0 mm",
            "mm",
            "Projected directly from the Rev6 PCB MIC1 2.0 mm NPTH.",
        )
        cover = root.bRepBodies.itemByName("Cover Plate")
        if not cover:
            raise RuntimeError("The root Cover Plate body was not found.")
        feature = _cut_mic_hole(root, cover, mic_root)
        design.computeAll()

        cylinders = _matching_cover_cylinders(cover, mic_root)
        if not cylinders:
            raise RuntimeError(
                "The cover cut completed but its 2.0 mm cylindrical face could not be verified."
            )

        axis_samples = []
        for z_mm in range(-5, 46):
            point = adsk.core.Point3D.create(mic_root.x, mic_root.y, z_mm / 10.0)
            axis_samples.append(
                {
                    "z_mm": z_mm,
                    "containment": int(cover.pointContainment(point)),
                }
            )
        if any(sample["containment"] == 0 for sample in axis_samples):
            raise RuntimeError("Solid cover material remains on the microphone axis.")

        report = {
            "document": app.activeDocument.name,
            "rev6_step_path": STEP_PATH,
            "old_rev2_top_occurrence": old_top.name,
            "old_rev2_retained": True,
            "old_rev2_visible": old_top.isVisible,
            "old_rev2_board_occurrence": old_board.fullPathName,
            "new_rev6_occurrence": new_occurrence.name,
            "new_rev6_component": new_occurrence.component.name,
            "placement_method": "Exact copy of OMOTE Rev2 Remote PCB world transform",
            "old_board_transform": _matrix_values(old_board.transform2),
            "new_board_transform": _matrix_values(new_occurrence.transform2),
            "transform_max_delta": max(
                abs(a - b)
                for a, b in zip(
                    _matrix_values(old_board.transform2),
                    _matrix_values(new_occurrence.transform2),
                )
            ),
            "mic_source": {
                "reference": "MIC1",
                "pcb_hole_diameter_mm": 2.0,
                "kicad_xy_mm": [142.5, 102.0],
                "step_xy_cm": [MIC_STEP_X_CM, MIC_STEP_Y_CM],
            },
            "mic_axis_root_cm": _point_values(mic_root),
            "cover_feature": feature.name,
            "verified_cover_cylinders": cylinders,
            "cover_axis_samples": axis_samples,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Rev6 PCB imported at the exact OMOTE Rev2 PCB transform.\n\n"
            "The Rev2 assembly is retained but hidden, and a verified 2.0 mm "
            "microphone opening has been cut through the front Cover Plate."
        )
    except Exception:
        if ui:
            ui.messageBox("Rev6 PCB/microphone update failed:\n" + traceback.format_exc())

