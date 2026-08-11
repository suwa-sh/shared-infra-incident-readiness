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
from . import contracts
import overlay_scoring as overlay_mod

OverlayError = defn_mod.OverlayError

# definition name -> (primary group holding the countable items, roles group or None)
_PRIMARY_GROUP = {
    "responsibility-matrix": ("resp", "roles"),
    "incident-raci": ("raci_act", "raci_roles"),
    "dpa-clauses": ("clauses", None),
    "notification-obligations": ("obligations", None),
    "scenarios": ("scenarios", None),
}


def summarize(overlay_paths: list[str | Path] | None = None, *, detail: bool = False) -> list[dict]:
    summaries = []
    # Route each overlay to the base its `extends` targets. An overlay that
    # matches no base raises (input error) instead of being silently dropped —
    # the old fallback showed the base and exited 0, hiding the mistake.
    definitions = defn_mod.load_all(overlay_paths)
    for name, (group_key, role_group_key) in _PRIMARY_GROUP.items():
        defn = definitions[name]
        sep = overlay_mod.separator_of(defn)
        groups = overlay_mod.group_items(defn)
        leaves = groups.get(group_key, {}).get("leaves", [])
        roles = groups.get(role_group_key, {}).get("leaves", []) if role_group_key else []
        summary = {
            "name": defn.get("name", name),
            "version": defn.get("version"),
            "array": group_key,
            "count": len(leaves),
            "ids": [defn_mod.local_id(i["id"], sep) for i in leaves],
            "roles": [defn_mod.local_id(r["id"], sep) for r in roles],
            "extension_points": defn.get("extension_points", []),
        }
        if detail:
            summary["items"] = [dict(item, id=defn_mod.local_id(item["id"], sep)) for item in leaves]
            summary["role_items"] = [
                dict(role, id=defn_mod.local_id(role["id"], sep)) for role in roles
            ]
        summaries.append(summary)
    return summaries


def check_overlay(overlay_path: str | Path) -> overlay_mod.MergeResult:
    """Validate an overlay against whichever base it declares via ``extends``."""
    ov = defn_mod.load_overlay_mapping(overlay_path)
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
    try:
        defn_mod.validate_overlay_compatibility(ov, base, overlay_path)
    except ValueError as error:
        return overlay_mod.MergeResult(
            merged={},
            violations=[
                overlay_mod.MergeViolation(
                    path="compatible_base_version",
                    kind="incompatible_base_version",
                    message=str(error),
                )
            ],
        )
    result = overlay_mod.apply_overlay(base, defn_mod.engine_overlay(ov))
    if not result.ok:
        return result
    try:
        # An overlay directory is one composable package. Cross-definition
        # references in a scenario file can therefore resolve through its
        # responsibility and RACI siblings, while a standalone custom overlay
        # is still checked against the base definitions.
        sibling_paths = sorted(Path(overlay_path).parent.glob("*.yaml"))
        defn_mod.load_all(sibling_paths or [overlay_path])
    except ValueError as error:
        return overlay_mod.MergeResult(
            merged=result.merged,
            violations=[
                overlay_mod.MergeViolation(
                    path="effective-definitions",
                    kind="semantic_reference",
                    message=str(error),
                )
            ],
        )
    return result


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


def render_json(
    summaries: list[dict], overlay_paths: list[str | Path] | None = None
) -> str:
    provenance = contracts.make_provenance(
        "list-definitions",
        definitions={
            summary["name"]: {
                "version": summary["version"],
                "summary": summary,
            }
            for summary in summaries
        },
        overlay_paths=overlay_paths,
    )
    return json.dumps(
        contracts.envelope(summaries, provenance), indent=2, ensure_ascii=False
    )


def render_overlay_text(result: overlay_mod.MergeResult) -> str:
    if result.ok:
        return "[OK] overlay valid (add / strengthen rules satisfied)"
    lines = [f"[NG] overlay rejected: {len(result.violations)} violations"]
    for v in result.violations:
        lines.append(f"  - {v.path}: {v.message} ({v.kind})")
    return "\n".join(lines)


def render_overlay_json(
    result: overlay_mod.MergeResult, overlay_path: str | Path | None = None
) -> str:
    payload = {
            "ok": result.ok,
            "violations": [{"path": v.path, "kind": v.kind, "message": v.message} for v in result.violations],
        }
    provenance = contracts.make_provenance(
        "check-overlay",
        definitions={"effective-overlay-target": result.merged} if result.merged else {},
        overlay_paths=[overlay_path] if overlay_path else None,
    )
    return json.dumps(
        contracts.envelope(payload, provenance),
        indent=2,
        ensure_ascii=False,
    )
