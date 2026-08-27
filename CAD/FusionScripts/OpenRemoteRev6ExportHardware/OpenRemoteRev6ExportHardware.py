import adsk.core
import adsk.fusion
import os
import traceback


WORKSPACE = "/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware"
MODEL_DIR = os.path.join(WORKSPACE, "CAD", "Hardware Models")
MODELS = (
    (
        "M3 x 8 mm Countersunk Phillips Screw",
        os.path.join(MODEL_DIR, "M3x8_Countersunk_Phillips_Screw.step"),
    ),
    (
        "M3 x 3 x 4.2 mm Heat-Set Insert",
        os.path.join(MODEL_DIR, "M3x3x4.2_Heat_Set_Insert.step"),
    ),
)


def _translation_length(matrix):
    vector = matrix.translation
    return (vector.x * vector.x + vector.y * vector.y + vector.z * vector.z) ** 0.5


def run(context):
    ui = None
    restored = []
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("The active Fusion document is not a Design.")

        root = design.rootComponent
        os.makedirs(MODEL_DIR, exist_ok=True)
        exported = []
        for component_prefix, path in MODELS:
            candidates = []
            for occurrence in root.occurrences:
                if occurrence.component.name.startswith(component_prefix):
                    candidates.append(occurrence)
            if not candidates:
                raise RuntimeError("Component not found: " + component_prefix)

            source = min(candidates, key=lambda item: _translation_length(item.transform2))
            component = source.component
            old_visibility = source.isLightBulbOn
            restored.append((source, old_visibility))
            source.isLightBulbOn = True

            options = design.exportManager.createSTEPExportOptions(path, component)
            if not design.exportManager.execute(options):
                raise RuntimeError("STEP export failed: " + path)
            source.isLightBulbOn = old_visibility
            restored.pop()
            exported.append(path)

        ui.messageBox(
            "Standalone hardware STEP files exported with solid geometry:\n\n"
            + "\n".join(exported)
        )
    except Exception:
        for occurrence, old_visibility in reversed(restored):
            try:
                occurrence.isLightBulbOn = old_visibility
            except Exception:
                pass
        if ui:
            ui.messageBox("Hardware STEP export failed:\n" + traceback.format_exc())
