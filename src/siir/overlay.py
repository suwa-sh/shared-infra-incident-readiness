"""Overlay loading and merge logic (generic, driven by ``extension_points``).

Each base definition declares its ``extension_points``. An overlay may only:

- ``add``        : append new items (with a fresh ``id``) to a declared array.
- ``strengthen`` : move a declared numeric field in the stricter direction only.

The stricter direction is *declared per field* in the base
(``direction: lower`` for SLA hours, ``direction: higher`` for thresholds),
so the semantics are explicit instead of hard-coded. Anything else
(overwrite, delete, weaken, unknown path) is a violation and rejected.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import yaml


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


def _parse_extension_points(base: dict) -> tuple[set[str], dict[tuple[str, str], str]]:
    """Return (add_paths, strengthen_specs) declared by the base definition.

    ``add_paths``        : set of top-level array keys that accept ``add``.
    ``strengthen_specs`` : {(array_key, field): direction} for ``strengthen``.
    """
    add_paths: set[str] = set()
    strengthen_specs: dict[tuple[str, str], str] = {}
    for ep in base.get("extension_points", []):
        if not isinstance(ep, dict):
            continue
        path = ep.get("path", "")
        allow = ep.get("allow")
        if allow == "add":
            add_paths.add(path)
        elif allow == "strengthen" and "[]." in path:
            array_key, fld = path.split("[].", 1)
            direction = ep.get("direction", "lower")
            if direction not in {"lower", "higher"}:
                direction = "lower"  # unknown direction is ambiguous; fail safe to "lower"
            strengthen_specs[(array_key, fld)] = direction
    return add_paths, strengthen_specs


def _apply_add(
    merged: dict,
    array_key: str,
    new_items: list,
    add_paths: set[str],
    violations: list[MergeViolation],
) -> None:
    if array_key not in add_paths:
        violations.append(
            MergeViolation(
                path=f"add.{array_key}",
                kind="unsupported_op",
                message=f"'{array_key}' is not an add-able extension point of this definition",
            )
        )
        return
    if not isinstance(new_items, list):
        violations.append(
            MergeViolation(
                path=f"add.{array_key}",
                kind="invalid_overlay",
                message=f"add.{array_key} must be a list",
            )
        )
        return
    existing = merged.setdefault(array_key, [])
    existing_ids = {x.get("id") for x in existing if isinstance(x, dict)}
    for item in new_items:
        if not isinstance(item, dict) or "id" not in item:
            violations.append(
                MergeViolation(
                    path=f"add.{array_key}",
                    kind="invalid_overlay",
                    message=f"each added item in {array_key} needs an 'id'",
                )
            )
            continue
        if item["id"] in existing_ids:
            violations.append(
                MergeViolation(
                    path=f"add.{array_key}[{item['id']}]",
                    kind="id_collision",
                    message=(
                        f"added id '{item['id']}' collides with an existing item; "
                        "use a unique id (overwrite is not allowed)"
                    ),
                )
            )
            continue
        existing.append(deepcopy(item))
        existing_ids.add(item["id"])


def _strengthen_field(target: dict, fld: str, new_val, direction: str, path: str) -> MergeViolation | None:
    """Apply one stricter-direction field update, or return a violation.

    strengthen targets are declared numeric; the new value must always be
    numeric, even when the base value is absent (otherwise a non-numeric value
    like "soon" could slip into a numeric field through an unset base).
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


def _strengthen_item(target: dict, fields, field_dirs: dict[str, str], base_path: str, violations: list[MergeViolation]) -> None:
    if not isinstance(fields, dict):
        violations.append(MergeViolation(path=base_path, kind="invalid_overlay", message="strengthen target must be a mapping of field -> value"))
        return
    for fld, new_val in fields.items():
        if fld not in field_dirs:
            violations.append(MergeViolation(path=f"{base_path}.{fld}", kind="unsupported_op", message=f"field '{fld}' is not declared strengthen-able"))
            continue
        v = _strengthen_field(target, fld, new_val, field_dirs[fld], f"{base_path}.{fld}")
        if v is not None:
            violations.append(v)


def _apply_strengthen(
    merged: dict,
    array_key: str,
    item_map: dict,
    strengthen_specs: dict[tuple[str, str], str],
    violations: list[MergeViolation],
) -> None:
    field_dirs = {f: d for (a, f), d in strengthen_specs.items() if a == array_key}
    if not field_dirs:
        violations.append(MergeViolation(path=f"strengthen.{array_key}", kind="unsupported_op", message=f"'{array_key}' has no strengthen-able fields declared"))
        return
    if not isinstance(item_map, dict):
        violations.append(MergeViolation(path=f"strengthen.{array_key}", kind="invalid_overlay", message=f"strengthen.{array_key} must be a mapping of id -> fields"))
        return
    index = {x.get("id"): x for x in merged.get(array_key, []) if isinstance(x, dict)}
    for item_id, fields in item_map.items():
        if item_id not in index:
            violations.append(MergeViolation(path=f"strengthen.{array_key}[{item_id}]", kind="unknown_id", message=f"id '{item_id}' is not in the base '{array_key}'"))
            continue
        _strengthen_item(index[item_id], fields, field_dirs, f"strengthen.{array_key}[{item_id}]", violations)


def apply_overlay(base: dict, overlay: dict) -> MergeResult:
    """Apply a single overlay onto ``base`` and return the merged definition."""
    violations: list[MergeViolation] = []

    if overlay.get("extends") != base.get("name"):
        violations.append(
            MergeViolation(
                path="extends",
                kind="extends_mismatch",
                message=(
                    f"overlay extends '{overlay.get('extends')}' does not match "
                    f"base name '{base.get('name')}'"
                ),
            )
        )
        return MergeResult(merged=deepcopy(base), violations=violations)

    add_paths, strengthen_specs = _parse_extension_points(base)
    merged = deepcopy(base)

    for key, value in overlay.get("add", {}).items():
        _apply_add(merged, key, value, add_paths, violations)

    for key, value in overlay.get("strengthen", {}).items():
        _apply_strengthen(merged, key, value, strengthen_specs, violations)

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
