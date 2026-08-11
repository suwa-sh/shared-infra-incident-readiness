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

from jsonschema import Draft202012Validator
import pytest

from siir import check_dpa as cd
from siir import check_responsibility as cr
from siir import contracts
from siir import definitions
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
    assert golden["contract_version"] == 1
    golden = golden["result"]
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


def test_list_definition_provenance_hashes_effective_definitions_not_view_shape():
    compact = json.loads(ld.render_json(ld.summarize()))
    detailed = json.loads(ld.render_json(ld.summarize(detail=True)))

    assert compact["provenance"]["definitions"] == detailed["provenance"]["definitions"]
    for name, definition in definitions.load_all().items():
        assert compact["provenance"]["definitions"][name]["digest"] == contracts._digest_object(definition)


def test_dpa03_confirmed_sla_is_72h_not_dropped(examples):
    """The 72h confirmed-report SLA (DPA03.sla_confirmed_hours) must survive
    the migration untouched — this is the specific breach the golden record
    fixture exercises (102h elapsed > 72h)."""
    result = vr.validate(examples / "records" / "sample-incident.json", level="extended")
    confirmed = next(
        finding
        for finding in result.sla_findings
        if finding.ref == "DPA03" and finding.sla_hours == pytest.approx(72.0)
    )
    assert confirmed.status == "breach"


def test_all_json_goldens_use_versioned_reproducible_envelope():
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "output-envelope.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    for path in sorted(GOLDEN.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(document)) == [], path.name
        assert document["contract_version"] == 1
        provenance = document["provenance"]
        assert provenance["tool_version"]
        assert provenance["overlay_engine_version"]
        for definition in provenance["definitions"].values():
            assert definition["digest"].startswith("sha256:")
