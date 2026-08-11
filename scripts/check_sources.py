#!/usr/bin/env python3
"""Validate source coverage and review dates for canonical decision data."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "definitions" / "source-registry.yaml"
TRACKED = {
    *(path.relative_to(ROOT).as_posix() for path in (ROOT / "definitions").glob("*.yaml") if path != REGISTRY),
    *(path.relative_to(ROOT).as_posix() for path in (ROOT / "overlays").glob("*/*.yaml")),
}
REQUIRED_SOURCE_FIELDS = {
    "id",
    "title",
    "authority",
    "source_kind",
    "jurisdiction",
    "url",
    "last_verified_on",
    "next_review_on",
    "applies_to",
}


def _as_date(value, label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"{label} must be YYYY-MM-DD, got {value!r}") from error


def _target_item_ids(relative: str) -> set[str]:
    document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8")) or {}
    entries = document.get("items") if relative.startswith("definitions/") else document.get("add")
    ids = set()
    for item in entries or []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        item_id = item["id"]
        if "." in item_id:
            ids.add(item_id.split(".", 1)[1])
    return ids


def _check_dates(source_id: str, source: dict, today: date) -> list[str]:
    errors = []
    try:
        verified = _as_date(source["last_verified_on"], f"{source_id}.last_verified_on")
        next_review = _as_date(source["next_review_on"], f"{source_id}.next_review_on")
    except ValueError as error:
        return [str(error)]
    if next_review <= verified:
        errors.append(f"{source_id}: next_review_on must be after last_verified_on")
    if today > next_review:
        errors.append(f"{source_id}: source review overdue since {next_review.isoformat()}")
    return errors


def _check_target(
    source_id: str,
    target: object,
    covered: set[str],
    covered_items: dict[str, set[str]],
) -> list[str]:
    if not isinstance(target, dict) or not isinstance(target.get("item_refs"), list):
        return [f"{source_id}: applies_to entries require path and item_refs list"]
    relative = str(target.get("path", ""))
    if relative not in TRACKED:
        return [f"{source_id}: unknown tracked path '{relative}'"]
    covered.add(relative)
    item_refs = {str(item) for item in target["item_refs"]}
    known_items = _target_item_ids(relative)
    if "*" in item_refs:
        covered_items[relative].update(known_items)
        return []
    covered_items[relative].update(item_refs & known_items)
    unknown_items = sorted(item_refs - known_items)
    if unknown_items:
        return [
            f"{source_id}: {relative} has unknown item ref(s): {', '.join(unknown_items)}"
        ]
    return []


def _check_source(
    source: object,
    index: int,
    today: date,
    seen_ids: set[str],
    covered: set[str],
    covered_items: dict[str, set[str]],
) -> list[str]:
    label = f"source[{index}]"
    if not isinstance(source, dict):
        return [f"{label} must be a mapping"]
    missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
    if missing:
        return [f"{label} missing field(s): {', '.join(missing)}"]
    source_id = str(source["id"])
    errors = [f"duplicate source id: {source_id}"] if source_id in seen_ids else []
    seen_ids.add(source_id)
    if not str(source["url"]).startswith("https://"):
        errors.append(f"{source_id}: url must use https")
    errors.extend(_check_dates(source_id, source, today))
    for target in source["applies_to"]:
        errors.extend(_check_target(source_id, target, covered, covered_items))
    return errors


def _coverage_errors(covered: set[str], covered_items: dict[str, set[str]]) -> list[str]:
    errors = [
        f"tracked decision data has no source coverage: {relative}"
        for relative in sorted(TRACKED - covered)
    ]
    for relative in sorted(TRACKED & covered):
        missing_items = sorted(_target_item_ids(relative) - covered_items[relative])
        if missing_items:
            errors.append(
                f"tracked decision data has uncovered item(s) in {relative}: "
                f"{', '.join(missing_items)}"
            )
    return errors


def check(today: date | None = None) -> list[str]:
    today = today or date.today()
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    errors: list[str] = []
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return ["source registry must be a mapping with schema_version: 1"]
    covered: set[str] = set()
    covered_items: dict[str, set[str]] = {relative: set() for relative in TRACKED}
    seen_ids: set[str] = set()
    for index, source in enumerate(data.get("sources", []), start=1):
        errors.extend(
            _check_source(source, index, today, seen_ids, covered, covered_items)
        )
    errors.extend(_coverage_errors(covered, covered_items))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", type=date.fromisoformat, help="Override today's date for tests")
    args = parser.parse_args(argv)
    errors = check(args.today)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(f"[OK] {len(TRACKED)} decision-data files have current source coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
