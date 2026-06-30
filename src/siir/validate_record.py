"""Validate an incident record and check its notification timeline against SLA.

Two passes:

1. JSON Schema validation against ``schemas/incident-record.schema.json``
   (level ``minimum`` or ``extended``). The format checker is enabled so that
   ``"format": "date-time"`` actually rejects bad timestamps — without the
   ``jsonschema[format-nongpl]`` extra it is a silent no-op.

2. SLA check: each notification entry references an obligation (OB*) or clause
   (DPA*). We compute elapsed hours from the deadline anchor (detected_at /
   confirmed_at) to ``sent_at`` and compare to the SLA. Numeric deadlines
   (24h / 72h / 30 days) yield a hard breach finding; vague statutory wording
   ("遅滞なく" / "速やか", no ``duration_hours``) is reported as informational.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from . import definitions as defn_mod

OverlayError = defn_mod.OverlayError
DEFAULT_SCHEMA = defn_mod.SCHEMAS_DIR / "incident-record.schema.json"


@dataclass
class SchemaViolation:
    path: str
    message: str


@dataclass
class SlaFinding:
    ref: str
    status: str  # ok | breach | pending | info
    message: str
    elapsed_hours: float | None = None
    sla_hours: float | None = None


@dataclass
class RecordResult:
    level: str
    schema_violations: list[SchemaViolation] = field(default_factory=list)
    sla_findings: list[SlaFinding] = field(default_factory=list)

    @property
    def conclusion(self) -> str:
        if self.schema_violations or any(f.status == "breach" for f in self.sla_findings):
            return "BLOCK"
        if any(f.status in {"pending", "info"} for f in self.sla_findings):
            return "REVISE"
        return "PASS"


def _build_validator(schema_path: Path, level: str) -> Draft202012Validator:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    schema_id = schema.get("$id", str(schema_path))
    resource = Resource.from_contents(schema, default_specification=DRAFT202012)
    registry: Registry = Registry().with_resource(schema_id, resource)
    sub_schema = {"$ref": f"{schema_id}#/$defs/incident_record_{level}"}
    return Draft202012Validator(
        sub_schema,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sla_for_ref(ref: str, stage: str, obligations: dict, clauses: dict) -> tuple[float | None, str, str]:
    """Return (sla_hours, anchor, label) for an OB*/DPA* reference.

    ``stage`` selects which contractual deadline applies: a DPA clause with both
    a first-report SLA (``sla_hours``) and a confirmed-report SLA
    (``sla_confirmed_hours``) uses the latter when stage == "confirmed", so the
    72h confirmed report is not falsely checked against the 24h first-report SLA.
    """
    if ref.startswith("OB") and ref in obligations:
        ob = obligations[ref]
        return ob.get("duration_hours"), ob.get("deadline_anchor", "awareness"), ob.get("name", ref)
    if ref.startswith("DPA") and ref in clauses:
        cl = clauses[ref]
        if stage == "confirmed" and cl.get("sla_confirmed_hours") is not None:
            return cl.get("sla_confirmed_hours"), "awareness", f"{cl.get('title', ref)} (確報)"
        return cl.get("sla_hours"), "awareness", cl.get("title", ref)
    return None, "awareness", ref


def validate(
    record_path: str | Path,
    level: str = "minimum",
    overlay_paths: list[str | Path] | None = None,
    schema_path: str | Path | None = None,
) -> RecordResult:
    if level not in {"minimum", "extended"}:
        raise ValueError(f"unknown level: {level}; expected 'minimum' or 'extended'")
    schema_path = Path(schema_path) if schema_path else DEFAULT_SCHEMA
    data = json.loads(Path(record_path).read_text(encoding="utf-8"))

    result = RecordResult(level=level)

    validator = _build_validator(schema_path, level)
    for err in validator.iter_errors(data):
        path = "/" + "/".join(str(p) for p in err.absolute_path)
        result.schema_violations.append(SchemaViolation(path=path, message=err.message))

    obligations = {
        o["id"]: o
        for o in defn_mod.load("notification-obligations", overlay_paths=overlay_paths).get("obligations", [])
    }
    clauses = {c["id"]: c for c in defn_mod.load("dpa-clauses", overlay_paths=overlay_paths).get("clauses", [])}

    detected = _parse_dt(data.get("detected_at"))
    confirmed = _parse_dt(data.get("confirmed_at"))

    for entry in data.get("notifications", []) or []:
        result.sla_findings.append(_evaluate_entry(entry, obligations, clauses, detected, confirmed))

    return result


def _evaluate_entry(entry: dict, obligations: dict, clauses: dict, detected, confirmed) -> SlaFinding:
    """Evaluate one notification entry against its referenced SLA."""
    ref = entry.get("obligation") or entry.get("clause") or "?"
    stage = entry.get("stage", "first")
    sla_hours, anchor, label = _sla_for_ref(ref, stage, obligations, clauses)
    anchor_dt = confirmed if anchor == "confirmation" and confirmed else detected
    sent = _parse_dt(entry.get("sent_at"))

    if entry.get("status") != "sent" or sent is None:
        return SlaFinding(ref=ref, status="pending", message=f"{label}: not sent yet ({entry.get('status')})")
    if sla_hours is None:
        return SlaFinding(ref=ref, status="info", message=f"{label}: non-numeric deadline; review manually")
    if anchor_dt is None:
        return SlaFinding(ref=ref, status="info", message=f"{label}: missing anchor timestamp")

    elapsed = (sent - anchor_dt).total_seconds() / 3600.0
    if elapsed < 0:
        return SlaFinding(
            ref=ref,
            status="breach",
            message=f"{label}: sent {-elapsed:.1f}h BEFORE {anchor} (timeline reversal)",
            elapsed_hours=elapsed,
            sla_hours=float(sla_hours),
        )
    if elapsed > float(sla_hours):
        return SlaFinding(
            ref=ref,
            status="breach",
            message=f"{label}: sent {elapsed:.1f}h after {anchor}, SLA is {sla_hours}h",
            elapsed_hours=elapsed,
            sla_hours=float(sla_hours),
        )
    return SlaFinding(
        ref=ref,
        status="ok",
        message=f"{label}: sent {elapsed:.1f}h after {anchor} (<= {sla_hours}h)",
        elapsed_hours=elapsed,
        sla_hours=float(sla_hours),
    )


_MARK = {"ok": "[OK]", "info": "[i]", "pending": "[..]", "breach": "[NG]"}


def render_text(result: RecordResult) -> str:
    lines = [f"Record schema: incident_record_{result.level}"]
    if result.schema_violations:
        lines.append(f"[NG] schema: {len(result.schema_violations)} violations")
        for v in result.schema_violations:
            lines.append(f"  - {v.path}: {v.message}")
    else:
        lines.append("[OK] schema: valid")
    lines.append("")
    lines.append("Notification SLA:")
    if not result.sla_findings:
        lines.append("  (no notification entries)")
    for f in result.sla_findings:
        lines.append(f"  {_MARK.get(f.status, '[??]')} {f.ref} {f.message}")
    lines.append("")
    lines.append(f"Conclusion: {result.conclusion}")
    return "\n".join(lines)


def render_json(result: RecordResult) -> str:
    return json.dumps(
        {
            "level": result.level,
            "conclusion": result.conclusion,
            "schema_violations": [{"path": v.path, "message": v.message} for v in result.schema_violations],
            "sla_findings": [
                {
                    "ref": f.ref,
                    "status": f.status,
                    "message": f.message,
                    "elapsed_hours": f.elapsed_hours,
                    "sla_hours": f.sla_hours,
                }
                for f in result.sla_findings
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def exit_code_for(result: RecordResult) -> int:
    return {"PASS": 0, "REVISE": 1, "BLOCK": 2}[result.conclusion]
