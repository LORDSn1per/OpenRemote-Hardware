import adsk.core
import adsk.fusion
import json
import os
import traceback


PILOT_DIAMETER_MM = 2.5
BOSS_DIAMETER_MM = 6.5
WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
REPORT_PATH = os.path.join(WORKSPACE, "CAD", "OpenRemoteRev6_direct_plastic_screws_report.json")
INSERT_NAME_FRAGMENT = "Heat-Set Insert"
OLD_FEATURE_NAME = "Rev6 M3 Heat-Set Insert Bores"
NEW_FEATURE_NAME = "Rev6 M3 Direct Plastic Pilot Bores"


def _find_named(collection, exact_name):
    item = collection.itemByName(exact_name)
    if item:
        return item
    for candidate in collection:
        if exact_name in candidate.name:
            return candidate
    return None


def _remove_insert_occurrences(root):
    removed = []
    # These are native lightweight components created by the Rev6 fastener
    # script, not the externally linked mirrored McMaster references.
    for _ in range(20):
        target = None
        for index in range(root.occurrences.count):
            occurrence = root.occurrences.item(index)
            if INSERT_NAME_FRAGMENT.lower() in occurrence.component.name.lower():
                target = occurrence
                break
        if not target:
            return removed
        removed.append(target.name)
        before = root.occurrences.count
        target.deleteMe()
        if root.occurrences.count >= before:
            raise RuntimeError("Fusion did not remove insert occurrence: " + target.name)
    raise RuntimeError("More than 20 heat-set insert occurrences were found.")


def _set_pilot_parameter(design):
    parameter = design.userParameters.itemByName("M3_Front_Pilot_Diameter")
    if parameter:
        parameter.expression = "2.5 mm"
        parameter.comment = "Pilot for an M3 machine screw threading directly into printed plastic."
    else:
        parameter = design.userParameters.add(
            "M3_Front_Pilot_Diameter",
            adsk.core.ValueInput.createByString("2.5 mm"),
            "mm",
            "Pilot for an M3 machine screw threading directly into printed plastic.",
        )
    for name in ("M3_Insert_Length", "M3_Insert_OD", "M3_Insert_Hole_Diameter"):
        obsolete = design.userParameters.itemByName(name)
        if obsolete:
            obsolete.deleteMe()


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
        sketch = _find_named(root.sketches, OLD_FEATURE_NAME + " Sketch")
        feature = _find_named(root.features.extrudeFeatures, OLD_FEATURE_NAME)
        plane = _find_named(root.constructionPlanes, OLD_FEATURE_NAME + " Plane")
        if not sketch:
            raise RuntimeError("Could not find the five heat-set insert bore circles.")

        circles = sketch.sketchCurves.sketchCircles
        if circles.count != 5:
            raise RuntimeError("Expected 5 boss pilot circles, found {}.".format(circles.count))
        for circle in circles:
            circle.radius = PILOT_DIAMETER_MM / 20.0

        sketch.name = NEW_FEATURE_NAME + " Sketch"
        if feature:
            feature.name = NEW_FEATURE_NAME
        if plane:
            plane.name = NEW_FEATURE_NAME + " Plane"

        _set_pilot_parameter(design)
        removed = _remove_insert_occurrences(root)
        design.computeAll()

        remaining_inserts = []
        screws = []
        for index in range(root.occurrences.count):
            occurrence = root.occurrences.item(index)
            component_name = occurrence.component.name
            if INSERT_NAME_FRAGMENT.lower() in component_name.lower():
                remaining_inserts.append(occurrence.name)
            if "M3 x 8 mm Countersunk Phillips Screw" in component_name and occurrence.isVisible:
                screws.append(occurrence.name)

        actual_diameters = [circle.radius * 20.0 for circle in circles]
        report = {
            "document": app.activeDocument.name,
            "heat_set_insert_occurrences_removed": removed,
            "remaining_heat_set_insert_occurrences": remaining_inserts,
            "direct_screw_pilot_diameter_mm": PILOT_DIAMETER_MM,
            "pilot_circle_diameters_mm": actual_diameters,
            "boss_diameter_mm": BOSS_DIAMETER_MM,
            "radial_plastic_wall_mm": (BOSS_DIAMETER_MM - PILOT_DIAMETER_MM) / 2.0,
            "visible_m3x8_screw_occurrences": screws,
            "feature_name": feature.name if feature else None,
            "sketch_name": sketch.name,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        if remaining_inserts:
            raise RuntimeError("Some heat-set insert occurrences remain: " + ", ".join(remaining_inserts))
        if len(screws) != 5:
            raise RuntimeError("Expected 5 visible M3x8 screws, found {}.".format(len(screws)))
        if any(abs(diameter - PILOT_DIAMETER_MM) > 1e-6 for diameter in actual_diameters):
            raise RuntimeError("One or more pilot holes did not update to 2.5 mm.")

        ui.messageBox(
            "Direct-plastic M3 conversion complete.\n\n"
            "Removed {} heat-set insert occurrences.\n"
            "Changed all five front-cover boss pilots from 3.8 mm to 2.5 mm.\n"
            "The 6.5 mm bosses now retain 2.0 mm radial plastic wall.\n"
            "All five M3x8 screw models remain in their existing positions."
            .format(len(removed))
        )
    except Exception:
        if ui:
            ui.messageBox("Direct-plastic M3 conversion failed:\n" + traceback.format_exc())

