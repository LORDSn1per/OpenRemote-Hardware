import adsk.core
import adsk.fusion
import json
import os
import traceback


REPORT_PATH = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware/CAD/OpenRemoteRev6_touch_fpc_report.json"

# J6 is the user-positioned 6-way touch connector in the current Rev6 PCB.
# These are read-only placement facts from OpenRemote.kicad_pcb.  The cable is
# built around them; this script does not move or modify the connector.
J6_KICAD_X_MM = 98.55
J6_KICAD_Y_MM = 82.15

# Existing Rev6 PCB-to-enclosure transform used by the Fusion assembly.
PCB_ROOT_X_OFFSET_CM = -10.2
PCB_ROOT_Y_OFFSET_CM = 13.417667696250028

CABLE_Z_MM = -2.90
CABLE_THICKNESS_MM = 0.12
CONTACT_THICKNESS_MM = 0.03


def _root_from_kicad(x_mm, y_mm):
    return (
        y_mm / 10.0 + PCB_ROOT_X_OFFSET_CM,
        -x_mm / 10.0 + PCB_ROOT_Y_OFFSET_CM,
    )


def _bbox(box):
    return {
        "min_cm": [box.minPoint.x, box.minPoint.y, box.minPoint.z],
        "max_cm": [box.maxPoint.x, box.maxPoint.y, box.maxPoint.z],
    }


def _appearance(app, design, name, rgb, terms):
    existing = design.appearances.itemByName(name)
    if existing:
        return existing
    source = None
    wanted = [term.lower() for term in terms]
    for library in app.materialLibraries:
        try:
            for candidate in library.appearances:
                lower = candidate.name.lower()
                if all(term in lower for term in wanted):
                    source = candidate
                    break
            if source:
                break
        except Exception:
            continue
    if not source:
        for library in app.materialLibraries:
            try:
                if library.appearances.count:
                    source = library.appearances.item(0)
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
            color_property.value = adsk.core.Color.create(*rgb, 255)
    except Exception:
        pass
    return result


def _offset_plane(component, offset_mm, name):
    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(
        component.xYConstructionPlane,
        adsk.core.ValueInput.createByString("{} mm".format(offset_mm)),
    )
    plane = component.constructionPlanes.add(plane_input)
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def _polygon(sketch, points_cm):
    lines = sketch.sketchCurves.sketchLines
    points = [adsk.core.Point3D.create(x, y, 0) for x, y in points_cm]
    for index in range(len(points)):
        lines.addByTwoPoints(points[index], points[(index + 1) % len(points)])


def _extrude_profiles(component, profiles, thickness_mm, name):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByString("{} mm".format(thickness_mm))
    )
    extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return feature


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
        component_name = "BuyDisplay Touch FPC - Verified Short Shape"
        # Replace only the previously generated cable component.  The PCB and
        # J6 connector are intentionally left untouched.
        replaced_count = 0
        for index in range(root.occurrences.count - 1, -1, -1):
            old_occurrence = root.occurrences.item(index)
            if old_occurrence.component.name == component_name:
                old_occurrence.deleteMe()
                replaced_count += 1
        design.computeAll()

        connector_x, connector_y = _root_from_kicad(
            J6_KICAD_X_MM, J6_KICAD_Y_MM
        )

        occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = component_name
        occurrence.component.partNumber = "BUYDISPLAY-TOUCH-FPC-REV6-SHORT"
        component = occurrence.component

        # The outline follows the user's red markup: a short insertion tongue,
        # a small shoulder, then a 7 mm-wide run extending toward the LCD.  The
        # earlier generated part had this direction mirrored toward the ESP32.
        tail_half = 0.175
        wide_left = connector_x - 0.45
        wide_right = connector_x + 0.25
        insertion_y = connector_y + 0.063
        shoulder_y = connector_y - 0.39
        under_display_y = connector_y - 2.74
        outline = [
            (connector_x - tail_half, insertion_y),
            (connector_x + tail_half, insertion_y),
            (connector_x + tail_half, shoulder_y),
            (wide_right, shoulder_y),
            (wide_right, under_display_y),
            (wide_left, under_display_y),
            (wide_left, shoulder_y),
            (connector_x - tail_half, shoulder_y),
        ]

        plane = _offset_plane(component, CABLE_Z_MM, "Touch FPC Plane")
        cable_sketch = component.sketches.add(plane)
        cable_sketch.name = "Verified Short Touch FPC Outline"
        _polygon(cable_sketch, outline)
        if cable_sketch.profiles.count != 1:
            raise RuntimeError(
                "Expected one cable profile; found {}.".format(
                    cable_sketch.profiles.count
                )
            )
        cable_feature = _extrude_profiles(
            component,
            cable_sketch.profiles.item(0),
            CABLE_THICKNESS_MM,
            "Verified Short Touch FPC",
        )
        cable_body = cable_feature.bodies.item(0)
        cable_body.name = "BuyDisplay Touch FPC Cable"

        orange = _appearance(
            app,
            design,
            "OpenRemote Touch FPC Orange",
            (238, 139, 18),
            ["plastic", "orange"],
        )
        if orange:
            cable_body.appearance = orange

        # Six short exposed contact fingers at the real connector end.
        contact_plane = _offset_plane(
            component,
            CABLE_Z_MM + CABLE_THICKNESS_MM,
            "Touch FPC Contact Plane",
        )
        contact_sketch = component.sketches.add(contact_plane)
        contact_sketch.name = "Touch FPC Six Contact Fingers"
        finger_pitch = 0.05
        finger_width = 0.03
        finger_y0 = insertion_y
        finger_y1 = insertion_y - 0.28
        lines = contact_sketch.sketchCurves.sketchLines
        for index in range(6):
            cx = connector_x + (index - 2.5) * finger_pitch
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(cx - finger_width / 2, finger_y0, 0),
                adsk.core.Point3D.create(cx + finger_width / 2, finger_y1, 0),
            )
        contact_profiles = adsk.core.ObjectCollection.create()
        for profile in contact_sketch.profiles:
            contact_profiles.add(profile)
        contact_feature = _extrude_profiles(
            component,
            contact_profiles,
            CONTACT_THICKNESS_MM,
            "Touch FPC Contact Fingers",
        )
        gold = _appearance(
            app,
            design,
            "OpenRemote Touch FPC Gold Contacts",
            (205, 151, 35),
            ["metal", "gold"],
        )
        for body in contact_feature.bodies:
            body.name = "Touch FPC Contact"
            if gold:
                body.appearance = gold

        cable_sketch.isLightBulbOn = False
        contact_sketch.isLightBulbOn = False
        occurrence.isLightBulbOn = True
        design.computeAll()

        report = {
            "document": app.activeDocument.name,
            "connector_was_moved": False,
            "connector_reference": "J6",
            "connector_kicad_position_mm": [J6_KICAD_X_MM, J6_KICAD_Y_MM],
            "connector_root_position_cm": [connector_x, connector_y],
            "component": component_name,
            "replaced_incorrect_components": replaced_count,
            "direction_correction": "long run now extends toward LCD, not ESP32",
            "outline_root_xy_cm": outline,
            "cable_thickness_mm": CABLE_THICKNESS_MM,
            "cable_bbox": _bbox(cable_body.boundingBox),
            "contact_count": contact_feature.bodies.count,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        if contact_feature.bodies.count != 6:
            raise RuntimeError("Expected six contact fingers.")
        ui.messageBox(
            "Corrected BuyDisplay touch FPC created.\n\n"
            "The J6 PCB connector was not moved.\n"
            "The long cable section now runs toward the LCD, matching the red markup,\n"
            "instead of extending beneath the ESP32.\n"
            "and terminates at J6's exact Rev6 PCB coordinates."
        )
    except Exception:
        if ui:
            ui.messageBox("Touch FPC update failed:\n" + traceback.format_exc())
