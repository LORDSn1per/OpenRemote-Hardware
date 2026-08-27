import adsk.core
import adsk.fusion
import json
import os
import traceback


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_pogo_candidate_report.json",
)

# Candidate contact pairs, 10 mm centre-to-centre.  Y runs from the USB end
# (negative) toward the IR end (positive) in this assembly.
CANDIDATE_Y_MM = [-90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50]
CONTACT_X_MM = [-5, 5]


def _point(point):
    return [point.x, point.y, point.z]


def _bbox(box):
    return {"min_cm": _point(box.minPoint), "max_cm": _point(box.maxPoint)}


def _material_intervals(body, x_cm, y_cm):
    # PointContainment 0 is inside, 1 is on, 2 is outside.  Sample at 0.05 mm
    # so the shell surfaces can be located accurately enough for selecting a
    # nominal contact site; the final feature uses exact BRep geometry.
    intervals = []
    active = None
    start_mm = None
    last_mm = None
    for i in range(-600, 21):
        z_mm = i * 0.05
        state = int(
            body.pointContainment(
                adsk.core.Point3D.create(x_cm, y_cm, z_mm / 10.0)
            )
        )
        inside = state in (0, 1)
        if inside != active:
            if active:
                intervals.append([start_mm, last_mm])
            active = inside
            start_mm = z_mm if inside else None
        last_mm = z_mm
    if active:
        intervals.append([start_mm, last_mm])
    return intervals


def _nearby_leaf_occurrences(root, x_cm, y_cm, radius_cm=0.25):
    hits = []
    for occurrence in root.allOccurrences:
        if occurrence.childOccurrences.count:
            continue
        box = occurrence.boundingBox
        if not box:
            continue
        if box.maxPoint.x < x_cm - radius_cm or box.minPoint.x > x_cm + radius_cm:
            continue
        if box.maxPoint.y < y_cm - radius_cm or box.minPoint.y > y_cm + radius_cm:
            continue
        hits.append(
            {
                "full_path": occurrence.fullPathName,
                "visible": occurrence.isVisible,
                "bbox": _bbox(box),
            }
        )
    return hits


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")

        root = design.rootComponent
        case = root.bRepBodies.itemByName("Case")
        if not case:
            raise RuntimeError("The original rear Case body was not found.")

        samples = []
        for y_mm in CANDIDATE_Y_MM:
            pair = []
            for x_mm in CONTACT_X_MM:
                x_cm = x_mm / 10.0
                y_cm = y_mm / 10.0
                pair.append(
                    {
                        "xy_mm": [x_mm, y_mm],
                        "case_material_z_intervals_mm": _material_intervals(
                            case, x_cm, y_cm
                        ),
                        "nearby_leaf_occurrences": _nearby_leaf_occurrences(
                            root, x_cm, y_cm
                        ),
                    }
                )
            samples.append({"y_mm": y_mm, "pair": pair})

        report = {
            "document": app.activeDocument.name,
            "case_bbox": _bbox(case.boundingBox),
            "candidate_contact_spacing_mm": 10.0,
            "samples": samples,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox("Pogo candidate inspection written to:\n" + REPORT_PATH)
    except Exception:
        if ui:
            ui.messageBox("Pogo candidate inspection failed:\n" + traceback.format_exc())

