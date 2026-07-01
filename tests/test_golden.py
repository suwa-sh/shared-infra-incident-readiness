"""Golden-output regression tests captured *before* the canonical-model migration.

These lock the externally-visible behaviour (SLA lookups incl. the 72h
confirmed-report clock, runbook stage counts/order, RACI gray-zone handling)
so the flat-items/overlay rewrite cannot silently change results. Fixtures
live in ``tests/golden/*.json`` and were captured from the pre-migration CLI
(``siir <command> --format json``) against the same example inputs used
below. ``list-definitions`` is checked narrowly (ids/counts/roles) because its
``extension_points`` field is expected to change shape with the new
structured extension-point declarations.
"""

from __future__ import annotations

import json
from pathlib import Path

from siir import check_dpa as cd
from siir import check_responsibility as cr
from siir import list_definitions as ld
from siir import render_runbook as rb
from siir import tabletop as tt
from siir import validate_record as vr

GOLDEN = Path(__file__).resolve().parent / "golden"


def _golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def test_validate_record_matches_golden(examples):
    result = vr.validate(examples / "records" / "sample-incident.json", level="extended")
    assert json.loads(vr.render_json(result)) == _golden("validate-record.json")


def test_render_runbook_matches_golden(examples):
    model = rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand")
    assert json.loads(rb.render_json(model)) == _golden("render-runbook.json")


def test_check_responsibility_matches_golden(examples):
    result = cr.check(examples / "responsibility" / "sample-oem-mail.yaml")
    assert json.loads(cr.render_json(result)) == _golden("check-responsibility.json")


def test_check_dpa_matches_golden(examples):
    result = cd.check(examples / "dpa" / "sample-dpa-answers.yaml")
    assert json.loads(cd.render_json(result)) == _golden("check-dpa.json")


def test_tabletop_matches_golden(examples):
    model = tt.build("rce-6brand", answers_path=examples / "responsibility" / "sample-oem-mail.yaml")
    assert json.loads(tt.render_json(model)) == _golden("tabletop.json")


def test_list_definitions_ids_and_roles_match_golden():
    golden = _golden("list-definitions.json")
    summaries = ld.summarize()
    got = {s["name"]: s for s in summaries}
    want = {s["name"]: s for s in golden}
    assert set(got) == set(want)
    for name, w in want.items():
        g = got[name]
        assert g["version"] == w["version"]
        assert g["count"] == w["count"]
        assert g["ids"] == w["ids"]
        assert g["roles"] == w["roles"]


def test_dpa03_confirmed_sla_is_72h_not_dropped(examples):
    """The 72h confirmed-report SLA (DPA03.sla_confirmed_hours) must survive
    the migration untouched — this is the specific breach the golden record
    fixture exercises (102h elapsed > 72h)."""
    result = vr.validate(examples / "records" / "sample-incident.json", level="extended")
    confirmed = next(f for f in result.sla_findings if f.ref == "DPA03" and f.sla_hours == 72.0)
    assert confirmed.status == "breach"
