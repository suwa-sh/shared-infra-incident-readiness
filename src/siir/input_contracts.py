"""Versioned input contracts and definition-aware semantic validation."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from . import definitions as defn_mod
import overlay_scoring as overlay_mod


ANSWER_SCHEMA_VERSION = 1


def validate_schema_version(data: object, label: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    version = data.get("schema_version")
    if version != ANSWER_SCHEMA_VERSION:
        raise ValueError(
            f"{label} schema_version must be {ANSWER_SCHEMA_VERSION}, got {version!r}"
        )
    return data


def load_yaml_answers(path: str | Path, schema_filename: str, label: str) -> dict:
    data = validate_schema_version(overlay_mod.load_yaml(path), label)
    schema_path = defn_mod.SCHEMAS_DIR / schema_filename
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        rendered = []
        for error in errors:
            pointer = "/" + "/".join(str(part) for part in error.absolute_path)
            rendered.append(f"{pointer}: {error.message}")
        raise ValueError(f"{label} contract violation(s): {'; '.join(rendered)}")
    return data


def validate_responsibility_semantics(answers: dict, definition: dict) -> None:
    sep = overlay_mod.separator_of(definition)
    groups = overlay_mod.group_items(definition)
    known_items = {
        defn_mod.local_id(item["id"], sep)
        for item in groups.get("resp", {}).get("leaves", [])
    }
    known_roles = {
        defn_mod.local_id(role["id"], sep)
        for role in groups.get("roles", {}).get("leaves", [])
    }
    matrix = answers.get("matrix", {})
    unknown_items = sorted(set(matrix) - known_items)
    if unknown_items:
        raise ValueError(f"responsibility answers contain unknown item id(s): {', '.join(unknown_items)}")
    for item_id, cells in matrix.items():
        unknown_roles = sorted(set(cells) - known_roles)
        if unknown_roles:
            raise ValueError(
                f"responsibility item '{item_id}' contains unknown role id(s): "
                f"{', '.join(unknown_roles)}"
            )


def validate_dpa_semantics(answers: dict, definition: dict) -> None:
    sep = overlay_mod.separator_of(definition)
    known_items = {
        defn_mod.local_id(item["id"], sep)
        for item in overlay_mod.group_items(definition).get("clauses", {}).get("leaves", [])
    }
    unknown_items = sorted(set(answers.get("clauses", {})) - known_items)
    if unknown_items:
        raise ValueError(f"DPA answers contain unknown clause id(s): {', '.join(unknown_items)}")
