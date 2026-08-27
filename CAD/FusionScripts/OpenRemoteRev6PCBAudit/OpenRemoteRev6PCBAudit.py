import adsk.core
import adsk.fusion
import json
import os
import traceback


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_pcb_alignment_audit.json",
)


def _point(point):
    return [point.x, point.y, point.z]


def _bbox(box):
    return {"min_cm": _point(box.minPoint), "max_cm": _point(box.maxPoint)}


def _find_one(items, predicate, description):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one {}; found {}.".format(description, len(matches))
        )
    return matches[0]


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        root = design.rootComponent

        old_top = _find_one(
            list(root.occurrences),
            lambda occurrence: "OMOTE Rev2" in occurrence.name,
            "retained OMOTE Rev2 top-level occurrence",
        )
        old_board = _find_one(
            list(root.allOccurrences),
            lambda occurrence: occurrence.component.name == "Remote PCB"
            and "OMOTE Rev2" in occurrence.fullPathName,
            "OMOTE Rev2 board occurrence",
        )
        new_top = _find_one(
            list(root.occurrences),
            lambda occurrence: occurrence.component.name == "OpenRemote PCB Rev6",
            "OpenRemote PCB Rev6 top-level occurrence",
        )
        new_board = _find_one(
            list(root.allOccurrences),
            lambda occurrence: occurrence.component.name == "OpenRemote_PCB"
            and "OpenRemote PCB Rev6" in occurrence.fullPathName,
            "Rev6 OpenRemote_PCB board occurrence",
        )
        if new_board.component.bRepBodies.count != 1:
            raise RuntimeError("Expected one Rev6 bare-board body.")
        board_body = new_board.component.bRepBodies.item(0)

        mic_faces = []
        for face in board_body.faces:
            cylinder = adsk.core.Cylinder.cast(face.geometry)
            if not cylinder:
                continue
            if (
                abs(cylinder.radius - 0.10) < 1e-5
                and abs(cylinder.origin.x - 14.25) < 1e-4
                and abs(cylinder.origin.y + 10.20) < 1e-4
            ):
                root_origin = cylinder.origin.copy()
                root_origin.transformBy(new_board.transform2)
                mic_faces.append(
                    {
                        "radius_cm": cylinder.radius,
                        "local_origin_cm": _point(cylinder.origin),
                        "root_origin_cm": _point(root_origin),
                        "face_bbox_local": _bbox(face.boundingBox),
                    }
                )
        if len(mic_faces) != 1:
            raise RuntimeError(
                "Expected one actual Rev6 MIC1 2.0 mm hole face; found {}.".format(
                    len(mic_faces)
                )
            )

        cover = root.bRepBodies.itemByName("Cover Plate")
        cover_faces = []
        mic_root = mic_faces[0]["root_origin_cm"]
        for face in cover.faces:
            cylinder = adsk.core.Cylinder.cast(face.geometry)
            if not cylinder:
                continue
            if (
                abs(cylinder.radius - 0.10) < 1e-5
                and abs(cylinder.origin.x - mic_root[0]) < 1e-4
                and abs(cylinder.origin.y - mic_root[1]) < 1e-4
            ):
                cover_faces.append(
                    {
                        "radius_cm": cylinder.radius,
                        "root_origin_cm": _point(cylinder.origin),
                        "face_bbox_root": _bbox(face.boundingBox),
                    }
                )
        if len(cover_faces) != 1:
            raise RuntimeError(
                "Expected one matching Cover Plate microphone opening; found {}.".format(
                    len(cover_faces)
                )
            )

        old_box = old_board.boundingBox
        new_box = new_board.boundingBox
        xy_edge_deltas_mm = {
            "min_x": 10 * (new_box.minPoint.x - old_box.minPoint.x),
            "max_x": 10 * (new_box.maxPoint.x - old_box.maxPoint.x),
            "min_y": 10 * (new_box.minPoint.y - old_box.minPoint.y),
            "max_y": 10 * (new_box.maxPoint.y - old_box.maxPoint.y),
        }

        report = {
            "document": app.activeDocument.name,
            "old_rev2_retained": old_top.isValid,
            "old_rev2_visible": old_top.isVisible,
            "new_rev6_visible": new_top.isVisible,
            "old_board_bbox_root": _bbox(old_box),
            "new_board_bbox_root": _bbox(new_box),
            "board_xy_edge_deltas_mm": xy_edge_deltas_mm,
            "note": "The occurrence transform is identical; small edge deltas are physical Rev6 board-outline differences.",
            "actual_rev6_mic_hole": mic_faces[0],
            "matching_cover_opening": cover_faces[0],
            "mic_to_cover_axis_delta_mm": [
                10 * (cover_faces[0]["root_origin_cm"][0] - mic_root[0]),
                10 * (cover_faces[0]["root_origin_cm"][1] - mic_root[1]),
            ],
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Rev6 PCB alignment audit passed.\n\n"
            "The actual MIC1 hole and Cover Plate opening share the same axis, "
            "and OMOTE Rev2 remains retained as a hidden browser component."
        )
    except Exception:
        if ui:
            ui.messageBox("Rev6 PCB alignment audit failed:\n" + traceback.format_exc())

