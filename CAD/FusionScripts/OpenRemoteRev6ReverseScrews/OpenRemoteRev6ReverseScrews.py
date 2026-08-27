import adsk.core
import adsk.fusion
import json
import os
import traceback


AXES_CM = [
    (0.700000010430813, 7.887653096250012),
    (-2.1000000000000343, -2.87000000000021),
    (-1.7000000000001165, -9.87000000000021),
    (2.099999999999966, -2.870000000000235),
    (1.6999999999998838, -9.870000000000253),
]

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_reverse_screws_report.json",
)


def _body(component, name):
    result = component.bRepBodies.itemByName(name)
    if not result:
        raise RuntimeError("Required root body not found: " + name)
    return result


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


def _offset_plane(root, offset_expression, name):
    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByString(offset_expression),
    )
    plane = planes.add(plane_input)
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def _circle_profiles(root, plane, axes, radius_cm, sketch_name):
    sketch = root.sketches.add(plane)
    sketch.name = sketch_name
    circles = sketch.sketchCurves.sketchCircles
    for x, y in axes:
        circles.addByCenterRadius(adsk.core.Point3D.create(x, y, 0), radius_cm)
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    if profiles.count != len(axes):
        raise RuntimeError(
            "Expected {} profiles in {}, found {}".format(
                len(axes), sketch_name, profiles.count
            )
        )
    sketch.isLightBulbOn = False
    return profiles


def _extrude(
    root,
    profiles,
    distance_expression,
    operation,
    feature_name,
    participant_body=None,
):
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(profiles, operation)
    if participant_body:
        extrude_input.participantBodies = [participant_body]
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByString(distance_expression)
    )
    extrude_input.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.PositiveExtentDirection
    )
    feature = extrudes.add(extrude_input)
    feature.name = feature_name
    return feature


def _add_cylinders(
    root,
    axes,
    radius_cm,
    start_expression,
    distance_expression,
    operation,
    name,
    participant_body=None,
):
    plane = _offset_plane(root, start_expression, name + " Plane")
    profiles = _circle_profiles(root, plane, axes, radius_cm, name + " Sketch")
    return _extrude(
        root,
        profiles,
        distance_expression,
        operation,
        name,
        participant_body,
    )


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
        case = _body(root, "Case")
        cover = _body(root, "Cover Plate")
        if root.features.itemByName("Rev6 Front Blind Pilot Holes"):
            raise RuntimeError("The Rev6 reverse-screw features already exist.")

        _parameter(design, "M3_Screw_Length", "8 mm", "mm", "User-provided M3 screw length under the head.")
        _parameter(design, "M3_Rear_Access_Diameter", "5.8 mm", "mm", "Clear access for the existing socket-head style.")
        _parameter(design, "M3_Rear_Clearance_Diameter", "3.4 mm", "mm", "Free clearance for an M3 threaded shaft.")
        _parameter(design, "M3_Front_Pilot_Diameter", "2.8 mm", "mm", "Matches the previous rear-shell plastic pilot diameter.")
        _parameter(design, "M3_Front_Boss_Diameter", "6.5 mm", "mm", "Uses the five existing circular pads in the front shell.")
        _parameter(design, "M3_Rear_Head_Seat_Z", "-6.0 mm", "mm", "Places an 8 mm screw tip at +2.0 mm.")
        _parameter(design, "M3_Front_Pilot_End_Z", "2.6 mm", "mm", "Leaves 0.8 mm of solid front skin.")

        # A deep access bore lets each socket head drop to a common shoulder.
        # The smaller clearance bore then continues through the rear boss.
        _add_cylinders(
            root,
            AXES_CM,
            0.29,
            "-20 mm",
            "14 mm",
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            "Rev6 Rear Screw Head Access",
            case,
        )
        _add_cylinders(
            root,
            AXES_CM,
            0.17,
            "-6.0 mm",
            "5.6 mm",
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            "Rev6 Rear M3 Clearance Holes",
            case,
        )

        # Grow bosses down from the existing front-shell circular pads.  A
        # 0.1 mm PCB-side gap avoids merging with the legacy hidden PCB body.
        _add_cylinders(
            root,
            AXES_CM,
            0.325,
            "-0.4 mm",
            "3.9 mm",
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            "Rev6 Front Blind Bosses",
            cover,
        )
        _add_cylinders(
            root,
            AXES_CM,
            0.14,
            "-0.5 mm",
            "3.1 mm",
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            "Rev6 Front Blind Pilot Holes",
            cover,
        )

        hidden_screws = []
        for occurrence in root.occurrences:
            if "91292A110_18-8 Stainless Steel Socket Head Screw" in occurrence.name:
                occurrence.isLightBulbOn = False
                hidden_screws.append(occurrence.name)

        report = {
            "document": app.activeDocument.name,
            "axes_cm": AXES_CM,
            "rear_head_seat_z_mm": -6.0,
            "calculated_screw_tip_z_mm": 2.0,
            "front_pilot_end_z_mm": 2.6,
            "front_skin_inner_z_mm": 3.4,
            "front_skin_remaining_mm": 0.8,
            "hidden_legacy_front_inserted_screws": hidden_screws,
            "features": [
                "Rev6 Rear Screw Head Access",
                "Rev6 Rear M3 Clearance Holes",
                "Rev6 Front Blind Bosses",
                "Rev6 Front Blind Pilot Holes",
            ],
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Rev6 reverse-screw geometry created.\n\n"
            "The five legacy front-inserted screw occurrences were hidden. "
            "Inspect the rear access bores and front blind bosses before saving."
        )
    except Exception:
        if ui:
            ui.messageBox("Reverse-screw update failed:\n" + traceback.format_exc())
