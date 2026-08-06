"""Load canonical definitions and apply overlays.

The canonical YAML lives in ``definitions/`` at the repo root. Every command
that reads a definition goes through :func:`load` so overlays are resolved the
same way everywhere (Codex plan review: --overlay must apply to *all*
definition-reading commands, not just the check-* ones).
"""

from __future__ import annotations

from pathlib import Path

import overlay_scoring as overlay_mod

DEFINITIONS_DIR = Path(__file__).resolve().parents[2] / "definitions"
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"

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


_BASE_NAMES: dict[str, str] | None = None


def base_names() -> dict[str, str]:
    """definition key -> the base YAML's ``name:`` field (overlay ``extends`` target)."""
    global _BASE_NAMES
    if _BASE_NAMES is None:
        _BASE_NAMES = {
            key: (overlay_mod.load_yaml(definition_path(key)) or {}).get("name", key)
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
        ov = overlay_mod.load_yaml(path)
        if not isinstance(ov, dict):
            # a top-level list/scalar would AttributeError below and leak exit 1;
            # the CLI contract wants structural input errors as exit 3 (ValueError)
            raise ValueError(
                f"overlay '{path}' must be a YAML mapping with an 'extends' field"
            )
        extends = ov.get("extends")
        key = key_by_base.get(extends)
        if key is None:
            raise ValueError(
                f"overlay '{path}' extends unknown definition '{extends}' "
                f"(known: {', '.join(sorted(key_by_base))})"
            )
        routed[key].append(path)
    return routed


def load(
    name: str,
    overlay_paths: list[str | Path] | None = None,
    definition_path_override: str | Path | None = None,
) -> dict:
    """Load a definition by name, applying overlays (if any) in order."""
    path = Path(definition_path_override) if definition_path_override else definition_path(name)
    base = overlay_mod.load_yaml(path)
    overlay_paths = overlay_paths or []
    if not overlay_paths:
        return base
    result = overlay_mod.apply_overlays(base, overlay_paths)
    if not result.ok:
        raise OverlayError(result.violations)
    return result.merged
