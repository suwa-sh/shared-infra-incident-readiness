from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_sources.py"
SPEC = importlib.util.spec_from_file_location("check_sources", SCRIPT)
assert SPEC and SPEC.loader
check_sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_sources)


def test_source_registry_covers_all_decision_data():
    assert check_sources.check(date(2026, 8, 12)) == []


def test_source_registry_reports_overdue_reviews():
    errors = check_sources.check(date(2027, 2, 9))
    assert any("overdue" in error for error in errors)
