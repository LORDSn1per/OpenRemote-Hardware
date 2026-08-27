import adsk.core
import adsk.fusion
import json
import os
import traceback


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_pogo_case_report.json",
)

CASE_NAME = "Case"
POGO_CASE_NAME = "Case - Pogo Pins"
CONTACT_COMPONENT_NAME = "PG-F-3.0-2.0H Flat Receiver"

# Selected after sampling the live Rev6 v19 assembly.  This position is clear
# of bosses, battery hardware and populated PCB components, and its shell is
# almost exactly the receiver's nominal 2.0 mm height.
CONTACT_X_CM = (-0.5, 0.5)  # 10 mm centre-to-centre
CONTACT_Y_CM = -8.0

# Ordered RTLECS PG-F-3.0-2.0H nominal envelope.
HEAD_RADIUS_CM = 0.15
BODY_RADIUS_CM = 0.10
TOTAL_HEIGHT_CM = 0.20
HEAD_THICKNESS_CM = 0.04

# FDM assembly clearances and intended external proud height.
HEAD_POCKET_RADIUS_CM = 0.16
BODY_HOLE_RADIUS_CM = 0.11
PROUD_CM = 0.01


def _point(x, y, z):
    return adsk.core.Point3D.create(x, y, z)


def _vector(x, y, z):
    return adsk.core.Vector3D.create(x, y, z)


def _bbox(box):
    return {
        "min_cm": [box.minPoint.x, box.minPoint.y, box.minPoint.z],
        "max_cm": [box.maxPoint.x, box.maxPoint.y, box.maxPoint.z],
    }


def _inside(body, x, y, z):
    return int(body.pointContainment(_point(x, y, z))) in (0, 1)


def _axis_material_span(body, x, y):
    transitions = []
    previous = _inside(body, x, y, -3.0)
    previous_z = -3.0
    for i in range(-299, 2):
        z = i / 100.0
        current = _inside(body, x, y, z)
        if current != previous:
            lo = previous_z
            hi = z
            # Binary search the exact exterior/interior BRep transition.
            for _ in range(28):
                mid = (lo + hi) / 2.0
                if _inside(body, x, y, mid) == previous:
                    lo = mid
                else:
                    hi = mid
            transitions.append((lo + hi) / 2.0)
        previous = current
        previous_z = z
    if len(transitions) != 2:
        raise RuntimeError(
            "Expected one rear-shell material interval at ({:.1f}, {:.1f}) mm; "
            "found {} transitions.".format(x * 10, y * 10, len(transitions))
        )
    return transitions[0], transitions[1]


def _circular_cut(root, target, axes, radius_cm, start_cm, end_cm, name):
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane, adsk.core.ValueInput.createByReal(start_cm)
    )
    plane = root.constructionPlanes.add(plane_input)
    plane.name = name + " Plane"
    plane.isLightBulbOn = False

    sketch = root.sketches.add(plane)
    sketch.name = name + " Sketch"
    for x, y in axes:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(x, y, 0), radius_cm
        )
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    if profiles.count != len(axes):
        raise RuntimeError(
            "Expected {} profiles in {}; found {}.".format(
                len(axes), sketch.name, profiles.count
            )
        )
    sketch.isLightBulbOn = False

    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    extrude_input.participantBodies = [target]
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(end_cm - start_cm)
    )
    extrude_input.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.PositiveExtentDirection
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


def _cleanup_partial(root):
    # A previous interrupted run can leave its copy and temporary cutter base
    # feature in the timeline.  Remove only objects with this script's exact
    # names; the user's original Case is never touched.
    for name in (
        "Pogo Receiver Head Pockets",
        "Pogo Receiver Through Holes",
        "Pogo Receiver Cutting Tools",
    ):
        feature = root.features.itemByName(name)
        if feature:
            feature.deleteMe()
        sketch = root.sketches.itemByName(name + " Sketch")
        if sketch:
            sketch.deleteMe()
        plane = root.constructionPlanes.itemByName(name + " Plane")
        if plane:
            plane.deleteMe()

    for body in list(root.bRepBodies):
        if body.name.startswith("Pogo Receiver Cutting Tool"):
            body.deleteMe()

    copy_feature = root.features.copyPasteBodies.itemByName(
        "Duplicate Rear Case for Pogo Charging"
    )
    if copy_feature:
        copy_feature.deleteMe()
    else:
        partial_case = root.bRepBodies.itemByName(POGO_CASE_NAME)
        if partial_case:
            partial_case.deleteMe()


def _create_gold_appearance(app, design):
    name = "OpenRemote Gold Pogo Contact"
    existing = design.appearances.itemByName(name)
    if existing:
        return existing

    source = None
    for library in app.materialLibraries:
        try:
            for appearance in library.appearances:
                lower = appearance.name.lower()
                if "gold" in lower and ("polished" in lower or "shiny" in lower):
                    source = appearance
                    break
            if source:
                break
        except Exception:
            continue
    if not source:
        for library in app.materialLibraries:
            try:
                for appearance in library.appearances:
                    if "brass" in appearance.name.lower():
                        source = appearance
                        break
                if source:
                    break
            except Exception:
                continue
    if not source:
        return None

    result = design.appearances.addByCopy(source, name)
    try:
        color_property = adsk.core.ColorProperty.cast(
            result.appearanceProperties.itemByName("Color")
        )
        if color_property:
            color_property.value = adsk.core.Color.create(210, 155, 35, 255)
    except Exception:
        pass
    return result


def _make_receiver_component(root, placement, appearance):
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = _vector(placement[0], placement[1], placement[2])
    occurrence = root.occurrences.addNewComponent(matrix)
    component = occurrence.component
    component.name = CONTACT_COMPONENT_NAME
    component.partNumber = "PG-F-3.0-2.0H"
    component.description = (
        "RTLECS flat gold-plated charging target, 3.0 mm head diameter, "
        "2.0 mm nominal total height. Nominal model pending caliper verification."
    )

    head_sketch = component.sketches.add(component.xYConstructionPlane)
    head_sketch.name = "Pogo Receiver 3 mm Head Sketch"
    head_sketch.sketchCurves.sketchCircles.addByCenterRadius(
        _point(0, 0, 0), HEAD_RADIUS_CM
    )
    head_sketch.isLightBulbOn = False
    extrudes = component.features.extrudeFeatures
    head_input = extrudes.createInput(
        head_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    head_input.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(HEAD_THICKNESS_CM)
        ),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    head_feature = extrudes.add(head_input)
    head_feature.name = "Pogo Receiver 3 mm Head"

    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(
        component.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(HEAD_THICKNESS_CM),
    )
    body_plane = component.constructionPlanes.add(plane_input)
    body_plane.name = "Pogo Receiver Body Plane"
    body_plane.isLightBulbOn = False
    body_sketch = component.sketches.add(body_plane)
    body_sketch.name = "Pogo Receiver 2 mm Body Sketch"
    body_sketch.sketchCurves.sketchCircles.addByCenterRadius(
        _point(0, 0, 0), BODY_RADIUS_CM
    )
    body_sketch.isLightBulbOn = False
    body_input = extrudes.createInput(
        body_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    body_input.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByReal(TOTAL_HEIGHT_CM - HEAD_THICKNESS_CM)
        ),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    body_feature = extrudes.add(body_input)
    body_feature.name = "Pogo Receiver 2 mm Body"

    if component.bRepBodies.count != 1:
        raise RuntimeError(
            "Expected one joined pogo receiver body; found {}.".format(
                component.bRepBodies.count
            )
        )
    persisted = component.bRepBodies.item(0)
    persisted.name = "PG-F-3.0-2.0H Receiver"
    if appearance:
        persisted.appearance = appearance
    return occurrence, component, persisted


def _add_reference_parameter(design, name, expression, comment):
    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        existing.comment = comment
        return existing
    return design.userParameters.add(
        name,
        adsk.core.ValueInput.createByString(expression),
        "mm",
        comment,
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
            raise RuntimeError("Open the Rev6 root assembly before running this script.")

        root = design.rootComponent
        original_case = root.bRepBodies.itemByName(CASE_NAME)
        if not original_case:
            raise RuntimeError("The original rear Case body was not found.")
        receiver_occurrences = [
            occurrence
            for occurrence in root.occurrences
            if occurrence.component.name == CONTACT_COMPONENT_NAME
        ]
        receiver_geometry_valid = (
            len(receiver_occurrences) == 2
            and all(
                occurrence.boundingBox
                and occurrence.boundingBox.maxPoint.z
                - occurrence.boundingBox.minPoint.z
                > 0.1
                for occurrence in receiver_occurrences
            )
        )
        complete_existing = (
            root.bRepBodies.itemByName(POGO_CASE_NAME)
            and receiver_geometry_valid
            and root.features.itemByName("Pogo Receiver Through Holes")
            and root.features.itemByName("Pogo Receiver Head Pockets")
        )
        if complete_existing:
            raise RuntimeError("The pogo rear-case variant already exists.")
        for occurrence in reversed(receiver_occurrences):
            occurrence.deleteMe()
        _cleanup_partial(root)

        original_faces = original_case.faces.count
        spans = [
            _axis_material_span(original_case, x, CONTACT_Y_CM)
            for x in CONTACT_X_CM
        ]
        outer_z = sum(span[0] for span in spans) / len(spans)
        inner_z = sum(span[1] for span in spans) / len(spans)
        if abs(spans[0][0] - spans[1][0]) > 0.002:
            raise RuntimeError("The two selected exterior contact surfaces are not symmetric.")

        copy_feature = root.features.copyPasteBodies.add(original_case)
        copy_feature.name = "Duplicate Rear Case for Pogo Charging"
        if copy_feature.bodies.count != 1:
            raise RuntimeError("The rear-case copy did not produce exactly one body.")
        pogo_case = copy_feature.bodies.item(0)
        pogo_case.name = POGO_CASE_NAME

        axes = [(x, CONTACT_Y_CM) for x in CONTACT_X_CM]
        through_feature = _circular_cut(
            root,
            pogo_case,
            axes,
            BODY_HOLE_RADIUS_CM,
            outer_z - 0.10,
            inner_z + 0.10,
            "Pogo Receiver Through Holes",
        )
        pocket_feature = _circular_cut(
            root,
            pogo_case,
            axes,
            HEAD_POCKET_RADIUS_CM,
            outer_z - 0.10,
            outer_z + HEAD_THICKNESS_CM + 0.01,
            "Pogo Receiver Head Pockets",
        )

        appearance = _create_gold_appearance(app, design)
        receiver_face_z = outer_z - PROUD_CM
        first_occ, receiver_component, receiver_body = _make_receiver_component(
            root,
            (CONTACT_X_CM[0], CONTACT_Y_CM, receiver_face_z),
            appearance,
        )
        first_occ.attributes.add("OpenRemote", "Polarity", "+5V")

        second_matrix = adsk.core.Matrix3D.create()
        second_matrix.translation = _vector(
            CONTACT_X_CM[1], CONTACT_Y_CM, receiver_face_z
        )
        second_occ = root.occurrences.addExistingComponent(
            receiver_component, second_matrix
        )
        second_occ.attributes.add("OpenRemote", "Polarity", "GND")

        _add_reference_parameter(
            design,
            "Pogo_Target_Spacing",
            "10 mm",
            "Centre spacing between the two rear charging targets.",
        )
        _add_reference_parameter(
            design,
            "Pogo_Target_Head_Diameter",
            "3 mm",
            "Ordered PG-F-3.0-2.0H nominal flange diameter; verify on arrival.",
        )
        _add_reference_parameter(
            design,
            "Pogo_Target_Total_Height",
            "2 mm",
            "Ordered PG-F-3.0-2.0H nominal height; verify on arrival.",
        )
        _add_reference_parameter(
            design,
            "Pogo_Target_Proud",
            "0.1 mm",
            "Nominal target-face projection beyond the rear shell.",
        )

        original_case.isVisible = False
        pogo_case.isVisible = True
        first_occ.isLightBulbOn = True
        second_occ.isLightBulbOn = True
        design.computeAll()

        # Verify that the untouched original still has its original topology and
        # that both axes are completely open through the duplicated shell.
        if original_case.faces.count != original_faces:
            raise RuntimeError("The original Case body was unexpectedly modified.")
        residual = []
        for x in CONTACT_X_CM:
            inside_samples = []
            for i in range(-20, 21):
                z = outer_z + (inner_z - outer_z) * (i + 20) / 40.0
                if _inside(pogo_case, x, CONTACT_Y_CM, z):
                    inside_samples.append(z)
            residual.append(inside_samples)
        if any(residual):
            raise RuntimeError("Solid material remains on a pogo wire-hole axis.")

        report = {
            "document": app.activeDocument.name,
            "original_case": {
                "name": original_case.name,
                "visible": original_case.isVisible,
                "faces_before_and_after": [original_faces, original_case.faces.count],
            },
            "pogo_case": {
                "name": pogo_case.name,
                "visible": pogo_case.isVisible,
                "bbox": _bbox(pogo_case.boundingBox),
                "cut_features": [through_feature.name, pocket_feature.name],
            },
            "contact_centres_mm": [
                [x * 10, CONTACT_Y_CM * 10] for x in CONTACT_X_CM
            ],
            "shell_spans_mm": [
                [span[0] * 10, span[1] * 10] for span in spans
            ],
            "receiver_face_z_mm": receiver_face_z * 10,
            "receiver_occurrences": [
                {
                    "role": "Pogo Receiver +5V",
                    "occurrence": first_occ.name,
                    "bbox": _bbox(first_occ.boundingBox),
                },
                {
                    "role": "Pogo Receiver GND",
                    "occurrence": second_occ.name,
                    "bbox": _bbox(second_occ.boundingBox),
                },
            ],
            "nominal_receiver_mm": {
                "head_diameter": HEAD_RADIUS_CM * 20,
                "body_diameter": BODY_RADIUS_CM * 20,
                "total_height": TOTAL_HEIGHT_CM * 10,
                "head_thickness": HEAD_THICKNESS_CM * 10,
            },
            "printed_pockets_mm": {
                "head_diameter": HEAD_POCKET_RADIUS_CM * 20,
                "through_hole_diameter": BODY_HOLE_RADIUS_CM * 20,
                "external_proud": PROUD_CM * 10,
            },
            "polarity": (
                "+5V is x=-5 mm and GND is x=+5 mm when viewed from the rear "
                "with the IR end upward."
            ),
            "verification": {
                "original_untouched": True,
                "wire_hole_axes_clear": True,
                "nominal_dimensions_pending_physical_measurement": True,
            },
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Created '{}' with two nominal PG-F-3.0-2.0H receivers.\n\n"
            "Original '{}' is unchanged and hidden.\n"
            "Contact centres: X = -5/+5 mm, Y = -80 mm.\n"
            "Report: {}".format(POGO_CASE_NAME, CASE_NAME, REPORT_PATH)
        )
    except Exception:
        if ui:
            ui.messageBox("Pogo rear-case creation failed:\n" + traceback.format_exc())
