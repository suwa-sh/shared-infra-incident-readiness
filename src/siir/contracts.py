"""Stable output envelope and reproducibility metadata."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
from pathlib import Path
from typing import Any

import overlay_scoring


OUTPUT_CONTRACT_VERSION = 1


def _tool_version() -> str:
    try:
        return package_version("shared-infra-incident-readiness")
    except PackageNotFoundError:
        return "0.0.0.dev0"


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_object(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return _digest_bytes(encoded)


def _file_record(path: str | Path) -> dict[str, str]:
    resolved = Path(path)
    return {"name": resolved.name, "digest": _digest_bytes(resolved.read_bytes())}


def make_provenance(
    command: str,
    *,
    definitions: dict[str, dict] | None = None,
    input_paths: list[str | Path] | None = None,
    overlay_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    definition_records = {}
    for name, definition in sorted((definitions or {}).items()):
        definition_records[name] = {
            "version": definition.get("version"),
            "digest": _digest_object(definition),
        }
    overlays = []
    for order, path in enumerate(overlay_paths or [], start=1):
        overlays.append({"order": order, **_file_record(path)})
    return {
        "command": command,
        "tool_version": _tool_version(),
        "overlay_engine_version": overlay_scoring.__version__,
        "definitions": definition_records,
        "inputs": [_file_record(path) for path in input_paths or []],
        "overlays": overlays,
    }


def envelope(payload: object, provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": OUTPUT_CONTRACT_VERSION,
        "provenance": provenance,
        "result": payload,
    }


def render_text_footer(provenance: dict[str, Any]) -> str:
    definitions = ", ".join(
        f"{name}@{record.get('version')}"
        for name, record in provenance.get("definitions", {}).items()
    ) or "none"
    return (
        f"Provenance: contract=v{OUTPUT_CONTRACT_VERSION}; "
        f"siir={provenance.get('tool_version')}; "
        f"engine={provenance.get('overlay_engine_version')}; definitions={definitions}"
    )
