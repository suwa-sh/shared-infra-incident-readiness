"""Canonical overlay engine for readiness / scoring definitions.

A *definition* is a single flat ``items`` list. Every item has an ``id`` that is
either a **group header** (no separator, e.g. ``clauses``) or a **leaf**
(exactly one separator, e.g. ``clauses.DPA01``). The separator (default ``.``)
is fixed to one level: there are no ungrouped leaves and no deeper nesting.

A leaf's group prefix must reference an existing header. Group headers may carry
group-level numeric fields (thresholds, SLAs); leaves carry item fields plus any
*opaque* nested payload (``cells`` / ``recommended`` / ``injects`` / ``when`` ...)
that the engine never interprets.

The base declares its ``extension_points``. An overlay may only:

- ``add``        : append a new item (fresh ``id``) to a group the base allows.
- ``strengthen`` : move a declared numeric field toward the stricter direction.

The stricter direction is declared per field (``direction: lower`` for SLA hours,
``direction: higher`` for pass thresholds). Everything else (overwrite, delete,
weaken, unknown id, out-of-scope field) is a violation and rejected.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_SEPARATOR = "."


@dataclass
class MergeViolation:
    """A single rule-violation detected while applying an overlay."""

    path: str
    kind: str
    message: str


@dataclass
class MergeResult:
    """Outcome of applying overlays to a base definition."""

    merged: dict
    applied: list[str] = field(default_factory=list)
    violations: list[MergeViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def load_yaml(path: str | Path) -> dict:
    """Load a YAML file into a dict. Raises on syntax errors."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- id helpers -------------------------------------------------------------

def separator_of(defn: dict) -> str:
    return defn.get("separator", DEFAULT_SEPARATOR)


def is_leaf(item_id: str, sep: str) -> bool:
    return sep in item_id


def group_of(item_id: str, sep: str) -> str:
    """The group a header/leaf belongs to (the header's own id, or a leaf's prefix)."""
    return item_id.split(sep, 1)[0] if sep in item_id else item_id


def _depth_ok(item_id: str, sep: str) -> bool:
    """Fixed one level: an id has at most one separator."""
    return item_id.count(sep) <= 1


def _match_group(selector: str, group_id: str) -> bool:
    """Group selector: exact id, prefix family ('L*'), or '*' (all)."""
    if selector == "*":
        return True
    if selector.endswith("*"):
        return group_id.startswith(selector[:-1])
    return selector == group_id


# --- extension points -------------------------------------------------------

@dataclass
class StrengthenSpec:
    group_sel: str
    on: str  # "group" | "leaf"
    field: str
    direction: str  # "lower" | "higher"


def _parse_extension_points(base: dict) -> tuple[list[str], list[StrengthenSpec]]:
    """Return (add_selectors, strengthen_specs) declared by the base."""
    add_selectors: list[str] = []
    strengthen_specs: list[StrengthenSpec] = []
    for ep in base.get("extension_points", []):
        if not isinstance(ep, dict):
            continue
        allow = ep.get("allow")
        group_sel = ep.get("group", "*")
        if allow == "add":
            add_selectors.append(group_sel)
        elif allow == "strengthen":
            on = ep.get("level", "leaf")   # 'level' (not 'on'): 'on' is a YAML 1.1 boolean keyword
            if on not in {"group", "leaf"}:
                on = "leaf"
            direction = ep.get("direction", "lower")
            if direction not in {"lower", "higher"}:
                direction = "lower"  # ambiguous -> fail safe to lower (stricter = shorter)
            fld = ep.get("field")
            if fld:
                strengthen_specs.append(StrengthenSpec(group_sel, on, fld, direction))
    return add_selectors, strengthen_specs


# --- add --------------------------------------------------------------------

def _apply_add(
    merged: dict,
    new_items: list,
    add_selectors: list[str],
    sep: str,
    violations: list[MergeViolation],
) -> None:
    """Append new items in listed order. Leaf prefixes may reference headers
    added earlier in the same overlay (base + prior adds)."""
    if not isinstance(new_items, list):
        violations.append(
            MergeViolation(path="add", kind="invalid_overlay", message="'add' must be a list of items")
        )
        return
    items = merged.setdefault("items", [])
    existing_ids = {x.get("id") for x in items if isinstance(x, dict)}
    header_ids = {x["id"] for x in items if isinstance(x, dict) and "id" in x and not is_leaf(x["id"], sep)}

    for item in new_items:
        if not isinstance(item, dict) or "id" not in item:
            violations.append(
                MergeViolation(path="add", kind="invalid_overlay", message="each added item needs an 'id'")
            )
            continue
        new_id = item["id"]
        if not _depth_ok(new_id, sep):
            violations.append(
                MergeViolation(
                    path=f"add[{new_id}]",
                    kind="invalid_overlay",
                    message=f"id '{new_id}' has more than one '{sep}' (only one nesting level is allowed)",
                )
            )
            continue
        if new_id in existing_ids:
            violations.append(
                MergeViolation(
                    path=f"add[{new_id}]",
                    kind="id_collision",
                    message=f"added id '{new_id}' collides with an existing item (overwrite is not allowed)",
                )
            )
            continue
        grp = group_of(new_id, sep)
        if not any(_match_group(sel, grp) for sel in add_selectors):
            violations.append(
                MergeViolation(
                    path=f"add[{new_id}]",
                    kind="unsupported_op",
                    message=f"group '{grp}' is not an add-able extension point of this definition",
                )
            )
            continue
        if is_leaf(new_id, sep) and grp not in header_ids:
            violations.append(
                MergeViolation(
                    path=f"add[{new_id}]",
                    kind="unknown_group",
                    message=f"leaf '{new_id}' references group '{grp}' which does not exist",
                )
            )
            continue
        items.append(deepcopy(item))
        existing_ids.add(new_id)
        if not is_leaf(new_id, sep):
            header_ids.add(new_id)


# --- strengthen -------------------------------------------------------------

def _strengthen_one(
    target: dict, fld: str, new_val, direction: str, path: str
) -> MergeViolation | None:
    """Apply one stricter-direction field update, or return a violation.

    strengthen targets are numeric. The new value must be numeric even when the
    base value is absent, so a non-numeric value cannot slip in through an unset base.
    """
    try:
        new_f = float(new_val)
    except (TypeError, ValueError):
        return MergeViolation(path=path, kind="invalid_overlay", message=f"strengthen value for '{fld}' must be numeric")
    old = target.get(fld)
    if old is None:
        target[fld] = new_val
        return None
    try:
        old_f = float(old)
    except (TypeError, ValueError):
        return MergeViolation(path=path, kind="invalid_overlay", message=f"base value for '{fld}' is not numeric; cannot strengthen")
    weakened = new_f > old_f if direction == "lower" else new_f < old_f
    if weakened:
        return MergeViolation(
            path=path,
            kind="weakening_rejected",
            message=f"strengthen would weaken '{fld}' from {old} to {new_val} (stricter direction is '{direction}')",
        )
    target[fld] = new_val
    return None


def _apply_strengthen(
    merged: dict,
    item_map: dict,
    strengthen_specs: list[StrengthenSpec],
    sep: str,
    violations: list[MergeViolation],
) -> None:
    if not isinstance(item_map, dict):
        violations.append(
            MergeViolation(path="strengthen", kind="invalid_overlay", message="'strengthen' must be a mapping of id -> fields")
        )
        return
    index = {x.get("id"): x for x in merged.get("items", []) if isinstance(x, dict)}
    for item_id, fields in item_map.items():
        if item_id not in index:
            violations.append(
                MergeViolation(path=f"strengthen[{item_id}]", kind="unknown_id", message=f"id '{item_id}' is not in the definition")
            )
            continue
        if not isinstance(fields, dict):
            violations.append(
                MergeViolation(path=f"strengthen[{item_id}]", kind="invalid_overlay", message="strengthen target must be a mapping of field -> value")
            )
            continue
        on = "leaf" if is_leaf(item_id, sep) else "group"
        grp = group_of(item_id, sep)
        target = index[item_id]
        for fld, new_val in fields.items():
            spec = next(
                (s for s in strengthen_specs if s.on == on and s.field == fld and _match_group(s.group_sel, grp)),
                None,
            )
            if spec is None:
                violations.append(
                    MergeViolation(
                        path=f"strengthen[{item_id}].{fld}",
                        kind="unsupported_op",
                        message=f"field '{fld}' is not a declared strengthen-able {on} field for group '{grp}'",
                    )
                )
                continue
            v = _strengthen_one(target, fld, new_val, spec.direction, f"strengthen[{item_id}].{fld}")
            if v is not None:
                violations.append(v)


# --- validation & apply -----------------------------------------------------

def validate_definition(defn: dict) -> list[MergeViolation]:
    """Structural checks on a base definition (independent of any overlay)."""
    violations: list[MergeViolation] = []
    sep = separator_of(defn)
    items = defn.get("items", [])
    if not isinstance(items, list):
        return [MergeViolation(path="items", kind="invalid_definition", message="'items' must be a list")]
    seen: set[str] = set()
    header_ids: set[str] = set()
    for it in items:
        if not isinstance(it, dict) or "id" not in it:
            violations.append(MergeViolation(path="items", kind="invalid_definition", message="each item needs an 'id'"))
            continue
        iid = it["id"]
        if iid in seen:
            violations.append(MergeViolation(path=f"items[{iid}]", kind="id_collision", message=f"duplicate id '{iid}'"))
        seen.add(iid)
        if not _depth_ok(iid, sep):
            violations.append(MergeViolation(path=f"items[{iid}]", kind="invalid_definition", message=f"id '{iid}' has more than one '{sep}'"))
        if not is_leaf(iid, sep):
            header_ids.add(iid)
    for it in items:
        if isinstance(it, dict) and "id" in it and is_leaf(it["id"], sep):
            grp = group_of(it["id"], sep)
            if grp not in header_ids:
                violations.append(
                    MergeViolation(path=f"items[{it['id']}]", kind="unknown_group", message=f"leaf '{it['id']}' references missing group header '{grp}'")
                )
    return violations


def apply_overlay(base: dict, overlay: dict) -> MergeResult:
    """Apply a single overlay onto ``base`` and return the merged definition."""
    violations: list[MergeViolation] = []

    if overlay.get("extends") != base.get("name"):
        violations.append(
            MergeViolation(
                path="extends",
                kind="extends_mismatch",
                message=f"overlay extends '{overlay.get('extends')}' does not match base name '{base.get('name')}'",
            )
        )
        return MergeResult(merged=deepcopy(base), violations=violations)

    sep = separator_of(base)
    add_selectors, strengthen_specs = _parse_extension_points(base)
    merged = deepcopy(base)

    if "add" in overlay:
        _apply_add(merged, overlay["add"], add_selectors, sep, violations)
    if "strengthen" in overlay:
        _apply_strengthen(merged, overlay["strengthen"], strengthen_specs, sep, violations)

    for key in overlay:
        if key in {"version", "extends", "add", "strengthen"}:
            continue
        violations.append(
            MergeViolation(
                path=key,
                kind="unsupported_op",
                message=f"overlay top-level key '{key}' is not supported (use add / strengthen)",
            )
        )

    return MergeResult(merged=merged, violations=violations)


def apply_overlays(base: dict, overlay_paths: list[str | Path]) -> MergeResult:
    """Apply multiple overlays in order, stopping at the first that violates."""
    current = deepcopy(base)
    applied: list[str] = []
    all_violations: list[MergeViolation] = []
    for path in overlay_paths:
        overlay = load_yaml(path)
        result = apply_overlay(current, overlay)
        all_violations.extend(result.violations)
        if result.violations:
            return MergeResult(merged=result.merged, applied=applied, violations=all_violations)
        current = result.merged
        applied.append(str(path))
    return MergeResult(merged=current, applied=applied, violations=all_violations)


# --- projection helper (for consumers) --------------------------------------

def group_items(defn: dict) -> dict[str, dict]:
    """Regroup the flat ``items`` list into an ordered {group_id: {...}} map.

    Each entry is ``{"header": <header item or None>, "leaves": [<leaf items>]}``,
    preserving source order both across groups and within each group's leaves.
    Consumers use this instead of re-reading a nested structure.
    """
    sep = separator_of(defn)
    groups: dict[str, dict] = {}
    for it in defn.get("items", []):
        if not isinstance(it, dict) or "id" not in it:
            continue
        grp = group_of(it["id"], sep)
        g = groups.setdefault(grp, {"header": None, "leaves": []})
        if is_leaf(it["id"], sep):
            g["leaves"].append(it)
        else:
            g["header"] = it
    return groups
