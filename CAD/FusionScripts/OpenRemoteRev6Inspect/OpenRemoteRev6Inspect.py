import adsk.core
import adsk.fusion
import json
import os
import traceback


OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_fusion_inventory.json",
)

SCREW_AXES_CM = [
    [0.700000010430813, 7.887653096250012],
    [-2.1000000000000343, -2.87000000000021],
    [-1.7000000000001165, -9.87000000000021],
    [2.099999999999966, -2.870000000000235],
    [1.6999999999998838, -9.870000000000253],
]


def _point(point):
    return [point.x, point.y, point.z]


def _bbox(box):
    if not box:
        return None
    return {"min_cm": _point(box.minPoint), "max_cm": _point(box.maxPoint)}


def _matrix(matrix):
    return [matrix.getCell(row, col) for row in range(4) for col in range(4)]


def _component(component):
    return {
        "name": component.name,
        "part_number": component.partNumber,
        "bodies": [
            {
                "name": body.name,
                "visible": body.isVisible,
                "solid": body.isSolid,
                "appearance": body.appearance.name if body.appearance else None,
                "bbox": _bbox(body.boundingBox),
                "faces": body.faces.count,
            }
            for body in component.bRepBodies
        ],
        "sketches": [sketch.name for sketch in component.sketches],
        "features": [feature.name for feature in component.features],
    }


def _root_face_geometry(body):
    cylinders = []
    planes = []
    for index, face in enumerate(body.faces):
        geometry = face.geometry
        cylinder = adsk.core.Cylinder.cast(geometry)
        if cylinder:
            cylinders.append(
                {
                    "face_index": index,
                    "radius_cm": cylinder.radius,
                    "origin_cm": _point(cylinder.origin),
                    "axis": _point(cylinder.axis),
                    "bbox": _bbox(face.boundingBox),
                    "area_cm2": face.area,
                }
            )
            continue
        plane = adsk.core.Plane.cast(geometry)
        if plane:
            planes.append(
                {
                    "face_index": index,
                    "origin_cm": _point(plane.origin),
                    "normal": _point(plane.normal),
                    "bbox": _bbox(face.boundingBox),
                    "area_cm2": face.area,
                }
            )
    return {"cylinders": cylinders, "planes": planes}


def _axis_material_samples(body):
    result = []
    for x, y in SCREW_AXES_CM:
        samples = []
        last_value = None
        interval_start = None
        for step in range(-300, 51):
            z = step / 100.0
            value = int(body.pointContainment(adsk.core.Point3D.create(x, y, z)))
            if value != last_value:
                if last_value is not None:
                    samples.append(
                        {
                            "from_z_cm": interval_start,
                            "to_z_cm": (step - 1) / 100.0,
                            "containment": last_value,
                        }
                    )
                interval_start = z
                last_value = value
        samples.append(
            {"from_z_cm": interval_start, "to_z_cm": 0.5, "containment": last_value}
        )
        result.append({"axis_xy_cm": [x, y], "intervals": samples})
    return result


def _occurrence(occurrence):
    return {
        "name": occurrence.name,
        "full_path": occurrence.fullPathName,
        "visible": occurrence.isVisible,
        "grounded": occurrence.isGrounded,
        "referenced": occurrence.isReferencedComponent,
        "transform": _matrix(occurrence.transform2),
        "bbox": _bbox(occurrence.boundingBox),
        "component": _component(occurrence.component),
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
        payload = {
            "document_name": app.activeDocument.name,
            "design_type": int(design.designType),
            "root": _component(root),
            "occurrences": [_occurrence(occ) for occ in root.allOccurrences],
            "root_body_faces": {
                body.name: _root_face_geometry(body) for body in root.bRepBodies
            },
            "root_body_axis_material": {
                body.name: _axis_material_samples(body)
                for body in root.bRepBodies
                if body.name in ("Case", "Cover Plate", "PCB")
                or body.name.startswith("Cover plate ")
            },
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        ui.messageBox("OpenRemote Rev6 inventory written to:\n" + OUTPUT_PATH)
    except Exception:
        if ui:
            ui.messageBox("Inventory failed:\n" + traceback.format_exc())
