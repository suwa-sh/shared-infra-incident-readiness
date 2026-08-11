from __future__ import annotations

import yaml

from siir import definitions, list_definitions


def _write_yaml(tmp_path, name: str, data: dict):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_all_shipped_definitions_and_overlays_are_semantically_valid():
    root = definitions.DEFINITIONS_DIR.parent
    overlays = sorted((root / "overlays").glob("*/*.yaml"))
    definitions.load_all(overlays)


def test_definition_version_is_validated_at_runtime(tmp_path):
    base = {
        "version": 2,
        "name": "future-definition",
        "separator": ".",
        "items": [],
    }
    path = _write_yaml(tmp_path, "future.yaml", base)
    try:
        definitions.load("responsibility-matrix", definition_path_override=path)
    except ValueError as error:
        assert "version must be 1" in str(error)
    else:
        raise AssertionError("unsupported definition version was accepted")


def test_overlay_rejects_incompatible_base_version(tmp_path):
    overlay = _write_yaml(
        tmp_path,
        "incompatible.yaml",
        {
            "extends": "shared-infra-responsibility-matrix",
            "compatible_base_version": 2,
            "add": [],
        },
    )
    result = list_definitions.check_overlay(overlay)
    assert not result.ok
    assert result.violations[0].kind == "incompatible_base_version"


def test_overlay_rejects_unknown_scenario_focus_reference(tmp_path):
    overlay = _write_yaml(
        tmp_path,
        "unknown-focus.yaml",
        {
            "extends": "shared-infra-tabletop-scenarios",
            "compatible_base_version": 1,
            "add": [
                {
                    "id": "scenarios.unknown-focus",
                    "title": "unknown focus",
                    "focus_items": ["ZZ99"],
                }
            ],
        },
    )
    result = list_definitions.check_overlay(overlay)
    assert not result.ok
    assert result.violations[0].kind == "semantic_reference"
    assert "ZZ99" in result.violations[0].message


def test_overlay_rejects_unknown_sla_reference(tmp_path):
    overlay = _write_yaml(
        tmp_path,
        "unknown-obligation.yaml",
        {
            "extends": "shared-infra-incident-raci",
            "compatible_base_version": 1,
            "add": [
                {
                    "id": "raci_act.AC99",
                    "text": "unknown obligation",
                    "obligation_ref": "OB999",
                    "cells": {"oem_operator": "R/A"},
                }
            ],
        },
    )
    result = list_definitions.check_overlay(overlay)
    assert not result.ok
    assert result.violations[0].kind == "semantic_reference"
    assert "OB999" in result.violations[0].message
