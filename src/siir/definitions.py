"""Load canonical definitions and apply overlays.

The canonical YAML lives in ``definitions/`` at the repo root. Every command
that reads a definition goes through :func:`load` so overlays are resolved the
same way everywhere (Codex plan review: --overlay must apply to *all*
definition-reading commands, not just the check-* ones).
"""

from __future__ import annotations

import os
from pathlib import Path

import overlay_scoring as overlay_mod

PACKAGE_ROOT = Path(os.environ.get("SIIR_ROOT", Path(__file__).resolve().parents[2]))
DEFINITIONS_DIR = PACKAGE_ROOT / "definitions"
SCHEMAS_DIR = PACKAGE_ROOT / "schemas"
DEFINITION_SCHEMA_VERSION = 1

# definition name -> filename
DEFINITION_FILES = {
    "responsibility-matrix": "responsibility-matrix.yaml",
    "incident-raci": "incident-raci.yaml",
    "dpa-clauses": "dpa-clauses.yaml",
    "notification-obligations": "notification-obligations.yaml",
    "scenarios": "scenarios.yaml",
}


class OverlayError(Exception):
    """Raised when an overlay violates the merge rules."""

    def __init__(self, violations):
        self.violations = violations
        msg = "; ".join(f"{v.path}: {v.message}" for v in violations)
        super().__init__(f"overlay violations: {msg}")


def definition_path(name: str) -> Path:
    if name not in DEFINITION_FILES:
        raise KeyError(f"unknown definition '{name}'")
    return DEFINITIONS_DIR / DEFINITION_FILES[name]


def local_id(item_id: str, sep: str) -> str:
    """A leaf's id without its group prefix (``clauses.DPA01`` -> ``DPA01``).

    Answers / overlays / cross-references (obligation_ref, clause_ref,
    focus_items, ...) are all written in this short form, unaffected by which
    group an item lives in.
    """
    return item_id.split(sep, 1)[1] if sep in item_id else item_id


def load_overlay_mapping(path: str | Path) -> dict:
    """Load an overlay file, requiring a top-level YAML mapping.

    A top-level list/scalar would AttributeError deeper in the engine and leak
    exit 1; the CLI contract wants structural input errors as exit 3
    (ValueError). Shared by route_overlays, load and check-overlay so every
    overlay-reading path enforces the same shape.
    """
    ov = overlay_mod.load_yaml(path)
    if not isinstance(ov, dict):
        raise ValueError(f"overlay '{path}' must be a YAML mapping with an 'extends' field")
    return ov


def _validate_base_definition(base: object, path: Path) -> dict:
    if not isinstance(base, dict):
        raise ValueError(f"definition '{path}' must be a YAML mapping")
    if base.get("version") != DEFINITION_SCHEMA_VERSION:
        raise ValueError(
            f"definition '{path}' version must be {DEFINITION_SCHEMA_VERSION}, "
            f"got {base.get('version')!r}"
        )
    if not isinstance(base.get("name"), str) or not base["name"].strip():
        raise ValueError(f"definition '{path}' requires a non-empty string 'name'")
    if not isinstance(base.get("items"), list):
        raise ValueError(f"definition '{path}' requires an 'items' list")
    return base


def validate_overlay_compatibility(overlay: dict, base: dict, path: str | Path) -> None:
    # Overlays created before this contract implicitly target v1. Shipped
    # overlays declare the field explicitly; the fallback preserves v0.3 users.
    compatible = overlay.get("compatible_base_version", 1)
    if compatible != base["version"]:
        raise ValueError(
            f"overlay '{path}' requires base version {compatible!r}, "
            f"but '{base['name']}' is version {base['version']}"
        )


def engine_overlay(overlay: dict) -> dict:
    """Return the merge-engine payload, excluding SIIR contract metadata."""
    return {key: value for key, value in overlay.items() if key != "compatible_base_version"}


_BASE_NAMES: dict[str, str] | None = None


def base_names() -> dict[str, str]:
    """definition key -> the base YAML's ``name:`` field (overlay ``extends`` target)."""
    global _BASE_NAMES
    if _BASE_NAMES is None:
        _BASE_NAMES = {
            key: _validate_base_definition(
                overlay_mod.load_yaml(definition_path(key)), definition_path(key)
            ).get("name", key)
            for key in DEFINITION_FILES
        }
    return _BASE_NAMES


def route_overlays(overlay_paths: list[str | Path] | None) -> dict[str, list[str | Path]]:
    """Partition overlay files by the definition their ``extends`` targets.

    Commands that load several definitions at once (tabletop / render-runbook /
    list-definitions) must not apply every ``--overlay`` to every base — a
    responsibility overlay would then be rejected while loading scenarios. This
    routes each overlay to its own base, preserving the given order per base.
    An ``extends`` that matches no base definition is an input error (CLI exit
    3), never silently dropped. Single-definition commands keep passing their
    overlay list straight to :func:`load`, so a mismatched overlay there stays
    a hard error.
    """
    routed: dict[str, list[str | Path]] = {key: [] for key in DEFINITION_FILES}
    if not overlay_paths:
        return routed
    key_by_base = {base: key for key, base in base_names().items()}
    for path in overlay_paths:
        overlay = load_overlay_mapping(path)
        extends = overlay.get("extends")
        key = key_by_base.get(extends)
        if key is None:
            raise ValueError(
                f"overlay '{path}' extends unknown definition '{extends}' "
                f"(known: {', '.join(sorted(key_by_base))})"
            )
        base = _validate_base_definition(
            overlay_mod.load_yaml(definition_path(key)), definition_path(key)
        )
        validate_overlay_compatibility(overlay, base, path)
        routed[key].append(path)
    return routed


def load(
    name: str,
    overlay_paths: list[str | Path] | None = None,
    definition_path_override: str | Path | None = None,
) -> dict:
    """Load a definition by name, applying overlays (if any) in order."""
    path = Path(definition_path_override) if definition_path_override else definition_path(name)
    base = _validate_base_definition(overlay_mod.load_yaml(path), path)
    overlay_paths = overlay_paths or []
    if not overlay_paths:
        return base
    merged = base
    for ov_path in overlay_paths:
        overlay = load_overlay_mapping(ov_path)  # structural check first
        validate_overlay_compatibility(overlay, base, ov_path)
        result = overlay_mod.apply_overlay(merged, engine_overlay(overlay))
        if not result.ok:
            raise OverlayError(result.violations)
        merged = result.merged
    return merged


def load_all(overlay_paths: list[str | Path] | None = None) -> dict[str, dict]:
    """Load all effective definitions, then validate their cross-references."""
    routed = route_overlays(overlay_paths)
    loaded = {name: load(name, overlay_paths=routed[name]) for name in DEFINITION_FILES}
    validate_effective_definitions(loaded)
    return loaded


def _leaf_map(definition: dict, group: str) -> dict[str, dict]:
    sep = overlay_mod.separator_of(definition)
    return {
        local_id(item["id"], sep): item
        for item in overlay_mod.group_items(definition).get(group, {}).get("leaves", [])
    }


def _cell_reference_errors(label: str, cells: object, roles: set[str]) -> list[str]:
    if not isinstance(cells, dict):
        return [f"{label} cells must be a mapping"]
    unknown = sorted(set(cells) - roles)
    return [f"{label} references unknown role(s): {', '.join(unknown)}"] if unknown else []


def _raci_reference_errors(
    activity_id: str,
    activity: dict,
    obligations: dict[str, dict],
    clauses: dict[str, dict],
    raci_items: dict[str, dict],
) -> list[str]:
    errors = []
    references = (
        ("obligation_ref", obligations, "obligation"),
        ("clause_ref", clauses, "clause"),
        ("after", raci_items, "after"),
    )
    for field, known, label in references:
        reference = activity.get(field)
        if reference is not None and reference not in known:
            errors.append(
                f"RACI activity '{activity_id}' references unknown {label} '{reference}'"
            )
    return errors


def _scenario_reference_errors(
    scenario_id: str,
    scenario: dict,
    known_focus: set[str],
    resp_items: dict[str, dict],
) -> list[str]:
    errors = []
    focus_items = scenario.get("focus_items", [])
    if not isinstance(focus_items, list):
        errors.append(f"scenario '{scenario_id}' focus_items must be a list")
    else:
        unknown_focus = sorted(str(ref) for ref in focus_items if ref not in known_focus)
        if unknown_focus:
            errors.append(
                f"scenario '{scenario_id}' references unknown focus item(s): "
                f"{', '.join(unknown_focus)}"
            )
    branches = scenario.get("communication_branches", []) or []
    if not isinstance(branches, list):
        return [*errors, f"scenario '{scenario_id}' communication_branches must be a list"]
    for branch in branches:
        if not isinstance(branch, dict):
            errors.append(f"scenario '{scenario_id}' communication branch must be a mapping")
            continue
        reference = branch.get("responsibility_ref")
        if reference is not None and reference not in resp_items:
            errors.append(
                f"scenario '{scenario_id}' communication branch references unknown "
                f"responsibility '{reference}'"
            )
    return errors


def validate_effective_definitions(definitions: dict[str, dict]) -> None:
    """Reject domain-invalid references after all overlays have been merged."""
    resp = definitions["responsibility-matrix"]
    raci = definitions["incident-raci"]
    scenarios = definitions["scenarios"]
    obligations = _leaf_map(definitions["notification-obligations"], "obligations")
    clauses = _leaf_map(definitions["dpa-clauses"], "clauses")
    resp_items = _leaf_map(resp, "resp")
    resp_roles = set(_leaf_map(resp, "roles"))
    raci_items = _leaf_map(raci, "raci_act")
    raci_roles = set(_leaf_map(raci, "raci_roles"))
    errors: list[str] = []

    for item_id, item in resp_items.items():
        errors.extend(
            _cell_reference_errors(
                f"responsibility item '{item_id}'", item.get("recommended", {}), resp_roles
            )
        )

    for activity_id, activity in raci_items.items():
        errors.extend(
            _cell_reference_errors(
                f"RACI activity '{activity_id}'", activity.get("cells", {}), raci_roles
            )
        )
        errors.extend(
            _raci_reference_errors(activity_id, activity, obligations, clauses, raci_items)
        )

    known_focus = set(resp_items) | set(raci_items)
    for scenario_id, scenario in _leaf_map(scenarios, "scenarios").items():
        errors.extend(
            _scenario_reference_errors(scenario_id, scenario, known_focus, resp_items)
        )

    if errors:
        raise ValueError("effective definition validation failed: " + "; ".join(errors))
