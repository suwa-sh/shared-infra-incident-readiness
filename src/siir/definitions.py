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
