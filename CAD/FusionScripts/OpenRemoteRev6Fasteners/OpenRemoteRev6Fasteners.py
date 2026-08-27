import adsk.core
import adsk.fusion
import json
import math
import os
import traceback


AXES_CM = [
    (0.700000010430813, 7.887653096250012),
    (-2.1000000000000343, -2.87000000000021),
    (-1.7000000000001165, -9.87000000000021),
    (2.099999999999966, -2.870000000000235),
    (1.6999999999998838, -9.870000000000253),
]

WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
MODEL_DIR = os.path.join(WORKSPACE, "CAD", "Hardware Models")
REPORT_PATH = os.path.join(WORKSPACE, "CAD", "OpenRemoteRev6_fastener_report.json")
SCREW_STEP = os.path.join(MODEL_DIR, "M3x8_Countersunk_Phillips_Screw.step")
INSERT_STEP = os.path.join(MODEL_DIR, "M3x3x4.2_Heat_Set_Insert.step")

SCREW_COMPONENT = "M3 x 8 mm Countersunk Phillips Screw"
INSERT_COMPONENT = "M3 x 3 x 4.2 mm Heat-Set Insert"


def _point(x, y, z):
    return adsk.core.Point3D.create(x, y, z)


def _vector(x, y, z):
    return adsk.core.Vector3D.create(x, y, z)


def _bbox(box):
    if not box:
        return None
    return {
        "min_cm": [box.minPoint.x, box.minPoint.y, box.minPoint.z],
        "max_cm": [box.maxPoint.x, box.maxPoint.y, box.maxPoint.z],
    }


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


def _find_root_body(root, name):
    body = root.bRepBodies.itemByName(name)
    if not body:
        raise RuntimeError("Required root body not found: " + name)
    return body


def _create_appearance(app, design, name, rgb, search_terms):
    existing = design.appearances.itemByName(name)
    if existing:
        return existing

    source = None
    wanted = [term.lower() for term in search_terms]
    for library in app.materialLibraries:
        try:
            for appearance in library.appearances:
                lower = appearance.name.lower()
                if all(term in lower for term in wanted):
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
                    lower = appearance.name.lower()
                    if any(term in lower for term in wanted):
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
            color_property.value = adsk.core.Color.create(
                rgb[0], rgb[1], rgb[2], 255
            )
    except Exception:
        pass
    return result


def _union(manager, target, tool):
    ok = manager.booleanOperation(
        target, tool, adsk.fusion.BooleanTypes.UnionBooleanType
    )
    if not ok:
        raise RuntimeError("Temporary BRep union failed.")


def _difference(manager, target, tool):
    return manager.booleanOperation(
        target, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType
    )


def _add_temp_body(component, body, appearance, body_name):
    base = component.features.baseFeatures.add()
    base.name = body_name + " Base Feature"
    base.startEdit()
    added = component.bRepBodies.add(body, base)
    base.finishEdit()
    added.name = body_name
    if appearance:
        added.appearance = appearance
    return added


def _make_screw_component(app, design, root, appearance):
    manager = adsk.fusion.TemporaryBRepManager.get()

    # ISO-style M3 countersunk head: 6.0 mm diameter, 1.7 mm high.
    screw = manager.createCylinderOrCone(
        _point(0, 0, 0.0), 0.30, _point(0, 0, 0.17), 0.15
    )

    # Model the 0.5 mm pitch with shallow circumferential thread ridges.  This
    # is lightweight enough for five occurrences while remaining recognisable.
    core = manager.createCylinderOrCone(
        _point(0, 0, 0.17), 0.135, _point(0, 0, 0.77), 0.135
    )
    _union(manager, screw, core)
    tip = manager.createCylinderOrCone(
        _point(0, 0, 0.77), 0.135, _point(0, 0, 0.80), 0.045
    )
    _union(manager, screw, tip)

    ridge_count = 0
    center = 0.19
    while center < 0.765:
        z0 = max(0.17, center - 0.0125)
        z1 = min(0.77, center + 0.0125)
        up = manager.createCylinderOrCone(
            _point(0, 0, z0), 0.135, _point(0, 0, center), 0.15
        )
        down = manager.createCylinderOrCone(
            _point(0, 0, center), 0.15, _point(0, 0, z1), 0.135
        )
        _union(manager, screw, up)
        _union(manager, screw, down)
        ridge_count += 1
        center += 0.05

    # Cross recess in the head.  Failure here is cosmetic, so retain the
    # mechanically accurate envelope if a Fusion build rejects an OBB cut.
    recess_created = False
    try:
        for length, width in ((0.32, 0.065), (0.065, 0.32)):
            box = adsk.core.OrientedBoundingBox3D.create(
                _point(0, 0, 0.04),
                _vector(1, 0, 0),
                _vector(0, 1, 0),
                length,
                width,
                0.08,
            )
            cutter = manager.createBox(box)
            if not _difference(manager, screw, cutter):
                raise RuntimeError("Phillips recess boolean failed")
        recess_created = True
    except Exception:
        recess_created = False

    transform = adsk.core.Matrix3D.create()
    source_occurrence = root.occurrences.addNewComponent(transform)
    component = source_occurrence.component
    component.name = SCREW_COMPONENT
    component.partNumber = "M3-CSK-PH2-8-A2"
    component.description = (
        "M3 x 8 mm total-length, 0.5 mm pitch countersunk Phillips machine screw"
    )
    body = _add_temp_body(component, screw, appearance, "M3x8 Screw")
    return source_occurrence, component, body, ridge_count, recess_created


def _make_insert_component(app, design, root, appearance):
    manager = adsk.fusion.TemporaryBRepManager.get()

    # M3 x 3 mm x 4.2 mm catalogue insert.  D1=3.71 mm, D2=3.77 mm.
    profile = [
        (0.000, 0.1855),
        (0.030, 0.1855),
        (0.045, 0.2100),
        (0.120, 0.2100),
        (0.145, 0.1840),
        (0.165, 0.1840),
        (0.190, 0.2100),
        (0.255, 0.2100),
        (0.270, 0.1885),
        (0.300, 0.1885),
    ]
    insert = None
    for (z0, r0), (z1, r1) in zip(profile[:-1], profile[1:]):
        segment = manager.createCylinderOrCone(
            _point(0, 0, z0), r0, _point(0, 0, z1), r1
        )
        if insert is None:
            insert = segment
        else:
            _union(manager, insert, segment)

    bore = manager.createCylinderOrCone(
        _point(0, 0, -0.01), 0.15, _point(0, 0, 0.31), 0.15
    )
    if not _difference(manager, insert, bore):
        raise RuntimeError("Could not create the M3 insert bore.")

    transform = adsk.core.Matrix3D.create()
    source_occurrence = root.occurrences.addNewComponent(transform)
    component = source_occurrence.component
    component.name = INSERT_COMPONENT
    component.partNumber = "M3-L3-OD4.2-HEATSET"
    component.description = (
        "Brass heat-set insert, M3 internal thread, 3 mm length, 4.2 mm maximum OD"
    )
    body = _add_temp_body(component, insert, appearance, "M3 Heat-Set Insert")
    return source_occurrence, component, body


def _place_occurrences(root, first, component, axes, z_cm, prefix):
    result = []
    # Keep an identity-transform source occurrence hidden.  Fusion composes
    # copies relative to the component's source transform, so moving the source
    # first would offset every subsequent occurrence.
    first.isLightBulbOn = False
    for x, y in axes:
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = _vector(x, y, z_cm)
        occurrence = root.occurrences.addExistingComponent(component, matrix)
        occurrence.isLightBulbOn = True
        result.append(occurrence)
    return result


def _add_tool_bodies(root, temp_bodies, feature_name):
    base = root.features.baseFeatures.add()
    base.name = feature_name + " Tools"
    base.startEdit()
    added = []
    for index, body in enumerate(temp_bodies):
        item = root.bRepBodies.add(body, base)
        item.name = "{} Tool {:02d}".format(feature_name, index + 1)
        added.append(item)
    base.finishEdit()
    return added


def _cut_with_tools(root, target, tools, feature_name):
    collection = adsk.core.ObjectCollection.create()
    for body in tools:
        collection.add(body)
    combine_input = root.features.combineFeatures.createInput(target, collection)
    combine_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combine_input.isKeepToolBodies = False
    feature = root.features.combineFeatures.add(combine_input)
    feature.name = feature_name
    return feature


def _circular_cut(
    root,
    target,
    axes,
    start_cm,
    end_cm,
    start_radius_cm,
    end_radius_cm,
    feature_name,
):
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(start_cm),
    )
    plane = root.constructionPlanes.add(plane_input)
    plane.name = feature_name + " Plane"
    plane.isLightBulbOn = False

    sketch = root.sketches.add(plane)
    sketch.name = feature_name + " Sketch"
    for x, y in axes:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            _point(x, y, 0), start_radius_cm
        )
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    if profiles.count != len(axes):
        raise RuntimeError(
            "Expected {} profiles for {}, found {}".format(
                len(axes), feature_name, profiles.count
            )
        )
    sketch.isLightBulbOn = False

    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    extrude_input.participantBodies = [target]
    distance_cm = end_cm - start_cm
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(distance_cm)
    )
    extrude_input.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.PositiveExtentDirection
    )
    if abs(start_radius_cm - end_radius_cm) > 1e-8:
        taper = -math.atan((start_radius_cm - end_radius_cm) / distance_cm)
        extrude_input.taperAngle = adsk.core.ValueInput.createByReal(taper)
    feature = extrudes.add(extrude_input)
    feature.name = feature_name
    return feature


def _cleanup_failed_tools(root):
    feature = root.features.itemByName("Rev6 M3 Countersunk Seats Tools")
    if feature:
        feature.deleteMe()
    for body in list(root.bRepBodies):
        if body.name.startswith("Rev6 M3 Countersunk Seats Tool"):
            body.deleteMe()


def _cleanup_partial_update(root):
    for component_name in (SCREW_COMPONENT, INSERT_COMPONENT):
        for attempt in range(20):
            target = None
            for index in range(root.occurrences.count):
                occurrence = root.occurrences.item(index)
                if occurrence.component.name == component_name:
                    target = occurrence
                    break
            if not target:
                break
            before = root.occurrences.count
            target.deleteMe()
            if root.occurrences.count >= before:
                raise RuntimeError(
                    "Could not remove partial native occurrence: " + component_name
                )
        else:
            raise RuntimeError("Too many partial occurrences: " + component_name)

    for name in (
        "Rev6 M3 Heat-Set Insert Bores",
        "Rev6 M3 Countersunk Seats",
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


def _hide_legacy_screws(root):
    hidden = []
    for index in range(root.occurrences.count):
        occurrence = root.occurrences.item(index)
        if "91292A110_18-8 Stainless Steel Socket Head Screw" in occurrence.name:
            occurrence.isLightBulbOn = False
            hidden.append(occurrence.name)
    return hidden


def _export_step(design, component, path):
    export_manager = design.exportManager
    options = export_manager.createSTEPExportOptions(path, component)
    if not export_manager.execute(options):
        raise RuntimeError("STEP export failed: " + path)


def _axis_samples(body, axes):
    result = []
    for x, y in axes:
        values = []
        for z_mm in (-5, -4, 0, 10, 20, 26, 27, 30, 34, 35, 39, 40):
            value = body.pointContainment(_point(x, y, z_mm / 10.0))
            values.append({"z_mm": z_mm, "containment": int(value)})
        result.append({"axis_xy_cm": [x, y], "samples": values})
    return result


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        if not app.activeDocument.name.startswith("OpenRemote Hardware Rev6"):
            raise RuntimeError("Open the OpenRemote Hardware Rev6 assembly first.")

        root = design.rootComponent
        case = _find_root_body(root, "Case")
        cover = _find_root_body(root, "Cover Plate")
        _cleanup_failed_tools(root)
        _cleanup_partial_update(root)

        boss_diameter_mm = 6.5
        boss_parameter = design.userParameters.itemByName("M3_Front_Boss_Diameter")
        if boss_parameter:
            boss_diameter_mm = boss_parameter.value * 10.0
        insert_od_mm = 4.2
        radial_wall_mm = (boss_diameter_mm - insert_od_mm) / 2.0
        inserts_feasible = radial_wall_mm >= 1.0

        _parameter(
            design,
            "M3_Screw_Length",
            "8 mm",
            "mm",
            "User screw total length, including the countersunk head.",
        )
        _parameter(design, "M3_Screw_Pitch", "0.5 mm", "mm", "M3 coarse pitch.")
        _parameter(
            design,
            "M3_Countersunk_Head_Diameter",
            "6 mm",
            "mm",
            "Measured catalogue-style countersunk head envelope.",
        )
        _parameter(design, "M3_Insert_Length", "3 mm", "mm", "Selected shortest M3 insert.")
        _parameter(design, "M3_Insert_OD", "4.2 mm", "mm", "Catalogue maximum outside diameter.")
        _parameter(
            design,
            "M3_Insert_Hole_Diameter",
            "3.8 mm",
            "mm",
            "Heat-set pilot; 0.4 mm diametral interference before melting.",
        )
        _parameter(
            design,
            "M3_Front_Pilot_Diameter",
            "3.8 mm" if inserts_feasible else "2.8 mm",
            "mm",
            "Updated for heat-set inserts when feasible.",
        )

        # The countersunk head receives a matching internal tapered seat while
        # retaining the existing user-finished sloped rear openings.
        _circular_cut(
            root,
            case,
            AXES_CM,
            -0.56,
            -0.37,
            0.315,
            0.170,
            "Rev6 M3 Countersunk Seats",
        )

        if inserts_feasible:
            _circular_cut(
                root,
                cover,
                AXES_CM,
                -0.05,
                0.26,
                0.190,
                0.190,
                "Rev6 M3 Heat-Set Insert Bores",
            )

        steel = _create_appearance(
            app,
            design,
            "OpenRemote Medium Shiny Grey",
            (105, 108, 115),
            ("steel", "polished"),
        )
        brass = _create_appearance(
            app,
            design,
            "OpenRemote Brass Insert",
            (190, 125, 35),
            ("brass",),
        )

        screw_first, screw_component, screw_body, ridges, phillips = _make_screw_component(
            app, design, root, steel
        )
        screws = _place_occurrences(
            root,
            screw_first,
            screw_component,
            AXES_CM,
            -0.55,
            "M3x8 Countersunk Phillips Screw",
        )

        insert_first, insert_component, insert_body = _make_insert_component(
            app, design, root, brass
        )
        inserts = _place_occurrences(
            root,
            insert_first,
            insert_component,
            AXES_CM,
            -0.04,
            "M3x3x4.2 Heat-Set Insert",
        )
        for occurrence in inserts:
            occurrence.isLightBulbOn = inserts_feasible

        hidden_legacy = _hide_legacy_screws(root)

        os.makedirs(MODEL_DIR, exist_ok=True)
        _export_step(design, screw_component, SCREW_STEP)
        _export_step(design, insert_component, INSERT_STEP)

        report = {
            "document": app.activeDocument.name,
            "axes_cm": AXES_CM,
            "legacy_screws_hidden": hidden_legacy,
            "legacy_screws_retained_for_stability": True,
            "inserts_feasible": inserts_feasible,
            "boss_diameter_mm": boss_diameter_mm,
            "insert_od_mm": insert_od_mm,
            "radial_plastic_wall_mm": radial_wall_mm,
            "insert_pilot_diameter_mm": 3.8 if inserts_feasible else 2.8,
            "insert_length_mm": 3.0,
            "insert_start_z_mm": -0.4,
            "insert_end_z_mm": 2.6,
            "front_outer_surface_z_mm": 4.0,
            "minimum_solid_front_depth_mm": 1.4,
            "screw_total_length_mm": 8.0,
            "screw_head_top_z_mm": -5.5,
            "screw_tip_z_mm": 2.5,
            "screw_thread_pitch_mm": 0.5,
            "screw_thread_ridges": ridges,
            "phillips_recess_created": phillips,
            "screw_occurrences": [
                {"name": occ.name, "visible": occ.isVisible, "bbox": _bbox(occ.boundingBox)}
                for occ in screws
            ],
            "insert_occurrences": [
                {"name": occ.name, "visible": occ.isVisible, "bbox": _bbox(occ.boundingBox)}
                for occ in inserts
            ],
            "cover_axis_samples": _axis_samples(cover, AXES_CM),
            "exported_models": [SCREW_STEP, INSERT_STEP],
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Rev6 fasteners updated.\n\n"
            "Five M3x8 countersunk Phillips screws replaced the legacy screws.\n"
            + (
                "Five M3x3x4.2 brass heat-set inserts are fitted in 3.8 mm bores."
                if inserts_feasible
                else "The insert models were created but hidden because the bosses were too small."
            )
            + "\n\nStandalone STEP models were exported to CAD/Hardware Models."
        )
    except Exception:
        if ui:
            ui.messageBox("Rev6 fastener update failed:\n" + traceback.format_exc())
