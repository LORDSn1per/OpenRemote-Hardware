import adsk.core
import adsk.fusion
import json
import os
import traceback


OUTPUT_PATH = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware/CAD/Dock Rev6/Charging Dock Rev6 USB Inspect.json"


def _bbox(box):
    if not box:
        return None
    return {
        "min_mm": [box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10],
        "max_mm": [box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10],
    }


def _body(body):
    return {
        "name": body.name,
        "visible": body.isVisible,
        "solid": body.isSolid,
        "volume_cm3": body.volume,
        "face_count": body.faces.count,
        "bbox": _bbox(body.boundingBox),
    }


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")
        root = design.rootComponent
        top_level = []
        for occurrence in root.occurrences:
            top_level.append({
                "name": occurrence.name,
                "full_path": occurrence.fullPathName,
                "component": occurrence.component.name,
                "visible": occurrence.isLightBulbOn,
                "referenced": occurrence.isReferencedComponent,
                "bbox": _bbox(occurrence.boundingBox),
                "bodies": [_body(body) for body in occurrence.bRepBodies],
            })
        payload = {
            "document": app.activeDocument.name,
            "design_type": int(design.designType),
            "root_component": root.name,
            "root_bodies": [_body(body) for body in root.bRepBodies],
            "top_level_occurrences": top_level,
        }
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        ui.messageBox("Dock USB inspection written to:\n" + OUTPUT_PATH)
    except Exception:
        if ui:
            ui.messageBox("Dock USB inspection failed:\n" + traceback.format_exc())
