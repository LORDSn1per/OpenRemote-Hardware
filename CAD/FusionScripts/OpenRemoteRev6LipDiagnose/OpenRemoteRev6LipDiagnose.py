import adsk.core
import adsk.fusion
import json
import os
import traceback


OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "OpenRemoteRev6_lip_diagnosis.json",
)

# Features the lip is supposed to come from. Matching is substring, case-insensitive,
# so "39" also catches "Sketch39", "Sketch39 (2)", "sketch39_copy" etc.
SKETCH_HINTS = ("39",)
FEATURE_HINTS = ("45",)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _health_name(value):
    states = {
        0: "Healthy",
        1: "Suppressed",
        2: "WarningFeature",
        3: "ErrorFeature",
        4: "Unknown",
        5: "RolledBack",
    }
    for attr in dir(adsk.fusion.FeatureHealthStates):
        if attr.startswith("__"):
            continue
        if _safe(lambda: getattr(adsk.fusion.FeatureHealthStates, attr)) == value:
            return attr.replace("FeatureHealthState", "") or attr
    return states.get(value, "value=%s" % value)


def _bbox(box):
    if not box:
        return None
    return {
        "min_cm": [box.minPoint.x, box.minPoint.y, box.minPoint.z],
        "max_cm": [box.maxPoint.x, box.maxPoint.y, box.maxPoint.z],
        "size_mm": [
            (box.maxPoint.x - box.minPoint.x) * 10.0,
            (box.maxPoint.y - box.minPoint.y) * 10.0,
            (box.maxPoint.z - box.minPoint.z) * 10.0,
        ],
    }


def _sketch_detail(sketch):
    curves = _safe(lambda: sketch.sketchCurves.count, 0)
    profiles = _safe(lambda: sketch.profiles.count, 0)
    open_ends = 0
    try:
        # count sketch points that only one curve touches -> open loop endpoints
        for point in sketch.sketchPoints:
            connected = _safe(lambda: point.connectedEntities, None)
            if connected is not None and connected.count == 1:
                open_ends += 1
    except Exception:
        open_ends = None
    return {
        "name": sketch.name,
        "component": _safe(lambda: sketch.parentComponent.name),
        "visible": _safe(lambda: sketch.isVisible),
        "curves": curves,
        "profiles": profiles,
        "fully_constrained": _safe(lambda: sketch.isFullyConstrained),
        "open_endpoints": open_ends,
        "bbox": _bbox(_safe(lambda: sketch.boundingBox)),
        "health": _health_name(_safe(lambda: sketch.healthState, 0)),
        "error": _safe(lambda: sketch.errorOrWarningMessage) or None,
        # THIS is the usual culprit: a sketch that used to close a loop and now
        # does not produces zero profiles, and every extrude built on it dies.
        "no_profiles": profiles == 0,
    }


def _feature_detail(feature):
    detail = {
        "name": _safe(lambda: feature.name),
        "type": type(feature).__name__,
        "component": _safe(lambda: feature.parentComponent.name),
        "health": _health_name(_safe(lambda: feature.healthState, 0)),
        "error": _safe(lambda: feature.errorOrWarningMessage) or None,
        "suppressed": _safe(lambda: feature.isSuppressed),
    }
    if isinstance(feature, adsk.fusion.ExtrudeFeature):
        prof = _safe(lambda: feature.profile)
        count = None
        if prof is not None:
            count = _safe(lambda: prof.count, 1)
        detail.update(
            {
                "profile_count": count,
                "operation": _safe(lambda: feature.operation),
                "extent_type": _safe(lambda: feature.extentType),
                "bodies": _safe(lambda: [b.name for b in feature.bodies], []),
                "body_count": _safe(lambda: feature.bodies.count, 0),
                # an extrude that produces no body is the visible symptom
                "produced_nothing": _safe(lambda: feature.bodies.count, 0) == 0,
            }
        )
    return detail


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("Open the Fusion design first, then run this script.")
            return

        timeline = design.timeline
        report = {
            "document": _safe(lambda: app.activeDocument.name),
            "timeline_count": _safe(lambda: timeline.count, 0),
            "marker_position": _safe(lambda: timeline.markerPosition, 0),
            "rolled_back": None,
            "unhealthy": [],
            "matched_sketches": [],
            "matched_features": [],
            "all_sketches_without_profiles": [],
            "components": [],
        }
        report["rolled_back"] = (
            report["marker_position"] < report["timeline_count"]
        )

        # ---- walk the whole timeline, flag anything not healthy -------------
        for index in range(_safe(lambda: timeline.count, 0)):
            item = timeline.item(index)
            entity = _safe(lambda: item.entity)
            if entity is None:
                continue
            health = _safe(lambda: entity.healthState, 0)
            name = _safe(lambda: item.name) or _safe(lambda: entity.name) or "?"
            is_bad = health not in (0, None)
            if is_bad or _safe(lambda: item.isSuppressed, False):
                report["unhealthy"].append(
                    {
                        "timeline_index": index,
                        "name": name,
                        "type": type(entity).__name__,
                        "health": _health_name(health),
                        "error": _safe(lambda: entity.errorOrWarningMessage) or None,
                        "suppressed": _safe(lambda: item.isSuppressed),
                    }
                )

        # ---- every component: sketches with no profiles, matched items ------
        for comp in design.allComponents:
            comp_entry = {"name": comp.name, "sketches": [], "features": []}
            for sketch in comp.sketches:
                detail = _sketch_detail(sketch)
                comp_entry["sketches"].append(detail["name"])
                if detail["no_profiles"]:
                    report["all_sketches_without_profiles"].append(detail)
                if any(h.lower() in sketch.name.lower() for h in SKETCH_HINTS):
                    report["matched_sketches"].append(detail)
            for feature in comp.features:
                fname = _safe(lambda: feature.name) or ""
                comp_entry["features"].append(fname)
                if any(h.lower() in fname.lower() for h in FEATURE_HINTS):
                    report["matched_features"].append(_feature_detail(feature))
            report["components"].append(comp_entry)

        with open(OUTPUT_PATH, "w") as handle:
            json.dump(report, handle, indent=2)

        # ---- concise on-screen summary --------------------------------------
        lines = []
        lines.append("Document: %s" % report["document"])
        lines.append(
            "Timeline: %d features, marker at %d%s"
            % (
                report["timeline_count"],
                report["marker_position"],
                "  <-- ROLLED BACK" if report["rolled_back"] else "",
            )
        )
        lines.append("")

        if report["unhealthy"]:
            lines.append("UNHEALTHY / SUPPRESSED FEATURES (%d):" % len(report["unhealthy"]))
            for item in report["unhealthy"][:15]:
                lines.append(
                    "  [%d] %s  (%s)  %s"
                    % (
                        item["timeline_index"],
                        item["name"],
                        item["health"],
                        (item["error"] or "")[:70],
                    )
                )
        else:
            lines.append("No unhealthy or suppressed features in the timeline.")
        lines.append("")

        if report["all_sketches_without_profiles"]:
            lines.append(
                "SKETCHES WITH ZERO PROFILES (%d) - an extrude on these builds nothing:"
                % len(report["all_sketches_without_profiles"])
            )
            for item in report["all_sketches_without_profiles"][:15]:
                lines.append(
                    "  %s / %s  curves=%s open_ends=%s"
                    % (
                        item["component"],
                        item["name"],
                        item["curves"],
                        item["open_endpoints"],
                    )
                )
            lines.append("")

        if report["matched_sketches"]:
            lines.append("MATCHED SKETCHES:")
            for item in report["matched_sketches"]:
                lines.append(
                    "  %s / %s  profiles=%s curves=%s visible=%s"
                    % (
                        item["component"],
                        item["name"],
                        item["profiles"],
                        item["curves"],
                        item["visible"],
                    )
                )
            lines.append("")

        if report["matched_features"]:
            lines.append("MATCHED FEATURES:")
            for item in report["matched_features"]:
                lines.append(
                    "  %s / %s  %s  health=%s bodies=%s"
                    % (
                        item["component"],
                        item["name"],
                        item["type"],
                        item["health"],
                        item.get("body_count"),
                    )
                )
                if item.get("error"):
                    lines.append("      %s" % item["error"][:80])
            lines.append("")

        lines.append("Full report: %s" % OUTPUT_PATH)
        ui.messageBox("\n".join(lines), "Rev6 lip diagnosis")

    except Exception:
        if ui:
            ui.messageBox("Failed:\n%s" % traceback.format_exc())
