import adsk.core
import adsk.fusion
import json
import os
import traceback


FEATURE_NAMES = [
    "Rev6 Rear Boss Reinforcement Top",
    "Rev6 Rear Boss Reinforcement Middle",
    "Rev6 Rear Boss Reinforcement Bottom",
]

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_remove_rear_tubes_report.json",
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
            raise RuntimeError(
                "Open the OpenRemote Hardware Rev6 root assembly before running this script."
            )

        root = design.rootComponent
        suppressed = []
        already_suppressed = []
        missing = []
        for name in FEATURE_NAMES:
            feature = root.features.itemByName(name)
            if not feature:
                missing.append(name)
                continue
            if feature.isSuppressed:
                already_suppressed.append(name)
            else:
                feature.isSuppressed = True
                suppressed.append(name)

        design.computeAll()

        required = [
            "Rev6 Rear Screw Head Access",
            "Rev6 Rear M3 Clearance Holes",
            "Rev6 Front Blind Bosses",
            "Rev6 Front Blind Pilot Holes",
        ]
        retained = []
        for name in required:
            feature = root.features.itemByName(name)
            if not feature or feature.isSuppressed:
                raise RuntimeError("Required screw feature is missing or suppressed: " + name)
            retained.append(name)

        report = {
            "document": app.activeDocument.name,
            "suppressed": suppressed,
            "already_suppressed": already_suppressed,
            "missing": missing,
            "retained": retained,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        ui.messageBox(
            "Removed the exposed rear reinforcement cylinders.\n\n"
            "The sloped head-access holes, M3 clearance holes, and front blind bosses remain active."
        )
    except Exception:
        if ui:
            ui.messageBox("Rear-tube removal failed:\n" + traceback.format_exc())
