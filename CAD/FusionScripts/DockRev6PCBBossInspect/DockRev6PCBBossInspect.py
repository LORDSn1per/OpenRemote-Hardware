import adsk.core
import adsk.fusion
import json
import os
import traceback


OUTPUT_PATH = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware/CAD/Dock Rev6/Charging Dock Rev6 PCB Boss Inspect.json"


def bbox(box):
    if not box:
        return None
    return {
        "min_mm": [box.minPoint.x * 10, box.minPoint.y * 10, box.minPoint.z * 10],
        "max_mm": [box.maxPoint.x * 10, box.maxPoint.y * 10, box.maxPoint.z * 10],
    }


def matrix_data(matrix):
    return [matrix.getCell(row, col) for row in range(4) for col in range(4)]


def body_data(body):
    return {
        "name": body.name,
        "is_solid": body.isSolid,
        "volume_cm3": body.volume,
        "bbox": bbox(body.boundingBox),
        "face_count": body.faces.count,
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
        occurrences = []
        for occurrence in root.allOccurrences:
            if "lid" in occurrence.name.lower() or "lid" in occurrence.component.name.lower():
                occurrences.append({
                    "name": occurrence.name,
                    "full_path": occurrence.fullPathName,
                    "component": occurrence.component.name,
                    "referenced": occurrence.isReferencedComponent,
                    "transform": matrix_data(occurrence.transform2),
                    "bbox": bbox(occurrence.boundingBox),
                    "bodies": [body_data(body) for body in occurrence.bRepBodies],
                })
        payload = {
            "document": app.activeDocument.name,
            "design_type": int(design.designType),
            "root_component": root.name,
            "lid_occurrences": occurrences,
            "root_bodies": [body_data(body) for body in root.bRepBodies],
            "user_parameters": {
                design.userParameters.item(index).name: design.userParameters.item(index).expression
                for index in range(design.userParameters.count)
            },
        }
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        ui.messageBox("Dock base-lid inspection written to:\n" + OUTPUT_PATH)
    except Exception:
        if ui:
            ui.messageBox("Dock inspection failed:\n" + traceback.format_exc())
