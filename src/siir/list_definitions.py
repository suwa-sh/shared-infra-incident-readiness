"""Inspect the loaded definitions (and the effect of any overlays).

``list-definitions`` summarises every canonical definition: version, the main
array and its item ids, and the declared extension points. With ``--overlay``
the summary reflects the merged result, so a team can see exactly what their
overlays added or strengthened before running a check.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import definitions as defn_mod
from . import overlay as overlay_mod

OverlayError = defn_mod.OverlayError

# definition name -> (primary group holding the countable items, roles group or None)
_PRIMARY_GROUP = {
    "responsibility-matrix": ("resp", "roles"),
    "incident-raci": ("raci_act", "raci_roles"),
    "dpa-clauses": ("clauses", None),
    "notification-obligations": ("obligations", None),
    "scenarios": ("scenarios", None),
}


def summarize(overlay_paths: list[str | Path] | None = None) -> list[dict]:
    summaries = []
    for name, (group_key, role_group_key) in _PRIMARY_GROUP.items():
        # overlays only apply to the base they `extends`; skip mismatches silently.
        try:
            defn = defn_mod.load(name, overlay_paths=overlay_paths)
        except OverlayError:
            defn = defn_mod.load(name)  # show base on mismatch
        sep = overlay_mod.separator_of(defn)
        groups = overlay_mod.group_items(defn)
        leaves = groups.get(group_key, {}).get("leaves", [])
        roles = groups.get(role_group_key, {}).get("leaves", []) if role_group_key else []
        summaries.append(
            {
                "name": defn.get("name", name),
                "version": defn.get("version"),
                "array": group_key,
                "count": len(leaves),
                "ids": [defn_mod.local_id(i["id"], sep) for i in leaves],
                "roles": [defn_mod.local_id(r["id"], sep) for r in roles],
                "extension_points": defn.get("extension_points", []),
            }
        )
    return summaries


def check_overlay(overlay_path: str | Path) -> overlay_mod.MergeResult:
    """Validate an overlay against whichever base it declares via ``extends``."""
    ov = overlay_mod.load_yaml(overlay_path)
    extends = ov.get("extends")
    base = None
    for name in defn_mod.DEFINITION_FILES:
        candidate = defn_mod.load(name)
        if candidate.get("name") == extends:
            base = candidate
            break
    if base is None:
        return overlay_mod.MergeResult(
            merged={},
            violations=[
                overlay_mod.MergeViolation(
                    path="extends",
                    kind="extends_mismatch",
                    message=f"no base definition named '{extends}' (check the 'extends' field)",
                )
            ],
        )
    return overlay_mod.apply_overlay(base, ov)


def _fmt_ep(ep: dict) -> str:
    grp = ep.get("group", "*")
    if ep.get("allow") == "strengthen":
        return f"{grp}.{ep.get('field')}:strengthen({ep.get('direction')})"
    return f"{grp}:{ep.get('allow')}"


def render_text(summaries: list[dict]) -> str:
    lines = []
    for s in summaries:
        lines.append(f"{s['name']} (v{s['version']})")
        lines.append(f"  {s['array']}: {s['count']} ({', '.join(str(i) for i in s['ids'])})")
        if s["roles"]:
            lines.append(f"  roles: {', '.join(s['roles'])}")
        if s["extension_points"]:
            lines.append(f"  extension_points: {', '.join(_fmt_ep(ep) for ep in s['extension_points'])}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_json(summaries: list[dict]) -> str:
    return json.dumps(summaries, indent=2, ensure_ascii=False)


def render_overlay_text(result: overlay_mod.MergeResult) -> str:
    if result.ok:
        return "[OK] overlay valid (add / strengthen rules satisfied)"
    lines = [f"[NG] overlay rejected: {len(result.violations)} violations"]
    for v in result.violations:
        lines.append(f"  - {v.path}: {v.message} ({v.kind})")
    return "\n".join(lines)


def render_overlay_json(result: overlay_mod.MergeResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "violations": [{"path": v.path, "kind": v.kind, "message": v.message} for v in result.violations],
        },
        indent=2,
        ensure_ascii=False,
    )
