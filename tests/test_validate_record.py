import json

from siir import validate_record as vr


def test_sample_record_schema_valid_but_sla_breach(examples):
    result = vr.validate(examples / "records" / "sample-incident.json", level="extended")
    assert result.schema_violations == []
    # the confirmed-report DPA03 entry is sent ~102h after detection (>72h) => breach
    breaches = [f for f in result.sla_findings if f.status == "breach"]
    assert any(f.ref == "DPA03" for f in breaches)
    assert result.conclusion == "BLOCK"
    assert vr.exit_code_for(result) == 2


def test_confirmed_stage_uses_confirmed_sla(tmp_path):
    # a DPA03 confirmed report at 50h is within 72h (ok) but would breach 24h first-report SLA
    record = {
        "incident_id": "INC-C",
        "detected_at": "2026-06-23T00:00:00+00:00",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [
            {"clause": "DPA03", "stage": "confirmed", "sent_at": "2026-06-25T02:00:00+00:00", "status": "sent"}
        ],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    finding = next(f for f in result.sla_findings if f.ref == "DPA03")
    assert finding.status == "ok"  # 50h <= 72h confirmed SLA (would be breach against 24h)


def test_timeline_reversal_is_breach(tmp_path):
    record = {
        "incident_id": "INC-R",
        "detected_at": "2026-06-23T12:00:00+00:00",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [
            {"clause": "DPA03", "sent_at": "2026-06-23T06:00:00+00:00", "status": "sent"}
        ],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    finding = next(f for f in result.sla_findings if f.ref == "DPA03")
    assert finding.status == "breach"  # sent before detection
    assert result.conclusion == "BLOCK"


def test_both_obligation_and_clause_rejected(tmp_path):
    record = {
        "incident_id": "INC-B",
        "detected_at": "2026-06-23T00:00:00+00:00",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [
            {"obligation": "OB01", "clause": "DPA03", "sent_at": "2026-06-23T01:00:00+00:00", "status": "sent"}
        ],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    assert result.schema_violations  # oneOf rejects both present


def test_clean_record_passes(tmp_path):
    record = {
        "incident_id": "INC-1",
        "detected_at": "2026-06-23T09:00:00+09:00",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [
            {"clause": "DPA03", "recipient": "principal_isp", "sent_at": "2026-06-23T15:00:00+09:00", "status": "sent"}
        ],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    assert result.schema_violations == []
    assert result.conclusion == "PASS"


def test_bad_datetime_caught_by_format_checker(tmp_path):
    record = {
        "incident_id": "INC-2",
        "detected_at": "not-a-date",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    # without jsonschema[format-nongpl] this would silently pass
    assert any("detected_at" in v.path for v in result.schema_violations)
    assert result.conclusion == "BLOCK"


def test_missing_required_field_is_schema_violation(tmp_path):
    record = {"incident_id": "INC-3", "detected_at": "2026-06-23T09:00:00+09:00"}
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    assert result.schema_violations
    assert result.conclusion == "BLOCK"


def test_non_numeric_obligation_is_info(tmp_path):
    record = {
        "incident_id": "INC-4",
        "detected_at": "2026-06-23T09:00:00+09:00",
        "shared_component": {"name": "x"},
        "affected": {"brands": ["A"]},
        "notifications": [
            {"obligation": "OB03", "recipient": "mic", "sent_at": "2026-06-24T09:00:00+09:00", "status": "sent"}
        ],
    }
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    result = vr.validate(p, level="minimum")
    assert any(f.ref == "OB03" and f.status == "info" for f in result.sla_findings)
    assert result.conclusion == "REVISE"
