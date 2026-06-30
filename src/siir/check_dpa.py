"""Check a contract's coverage of the mandatory DPA clauses.

Input answers YAML::

    target: <contract name>
    clauses:
      DPA01: present
      DPA03: missing
      DPA07: partial

Status per clause: ``present`` / ``partial`` / ``missing`` (default: missing).
A required clause that is ``missing`` => BLOCK; ``partial`` => REVISE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import definitions as defn_mod
from . import overlay as overlay_mod

OverlayError = defn_mod.OverlayError

_STATUSES = {"present", "partial", "missing"}


@dataclass
class ClauseResult:
    id: str
    title: str
    required: bool
    status: str  # present | partial | missing


@dataclass
class DpaResult:
    target: str
    clauses: list[ClauseResult]
    conclusion: str  # PASS | REVISE | BLOCK

    @property
    def score(self) -> float:
        if not self.clauses:
            return 0.0
        present = sum(1 for c in self.clauses if c.status == "present")
        return present / len(self.clauses)


def _normalize_status(value) -> str:
    if value is None:
        return "missing"
    s = str(value).strip().lower()
    if s in {"present", "yes", "true", "y"}:
        return "present"
    if s in {"partial", "wip"}:
        return "partial"
    return "missing"


def check(
    answers_path: str | Path,
    overlay_paths: list[str | Path] | None = None,
    definition_path_override: str | Path | None = None,
) -> DpaResult:
    defn = defn_mod.load(
        "dpa-clauses",
        overlay_paths=overlay_paths,
        definition_path_override=definition_path_override,
    )
    answers = overlay_mod.load_yaml(answers_path) or {}
    statuses = answers.get("clauses", {}) or {}

    clauses: list[ClauseResult] = []
    for clause in defn["clauses"]:
        status = _normalize_status(statuses.get(clause["id"]))
        clauses.append(
            ClauseResult(
                id=clause["id"],
                title=clause.get("title", ""),
                required=bool(clause.get("required", True)),
                status=status,
            )
        )

    conclusion = "PASS"
    for c in clauses:
        if c.required and c.status == "missing":
            conclusion = "BLOCK"
            break
    else:
        if any(c.status in {"partial", "missing"} for c in clauses):
            conclusion = "REVISE"

    return DpaResult(
        target=answers.get("target", str(answers_path)),
        clauses=clauses,
        conclusion=conclusion,
    )


_MARK = {"present": "[OK]", "partial": "[..]", "missing": "[NG]"}


def render_text(result: DpaResult) -> str:
    lines = [f"Target: {result.target}", f"DPA coverage: {int(result.score * 100)}%", ""]
    for c in result.clauses:
        req = "required" if c.required else "optional"
        lines.append(f"{_MARK.get(c.status, '[??]')} {c.id} {c.title}: {c.status.upper()} ({req})")
    lines.append("")
    lines.append(f"Conclusion: {result.conclusion}")
    return "\n".join(lines)


def render_json(result: DpaResult) -> str:
    return json.dumps(
        {
            "target": result.target,
            "conclusion": result.conclusion,
            "score": result.score,
            "clauses": [
                {"id": c.id, "title": c.title, "required": c.required, "status": c.status}
                for c in result.clauses
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def exit_code_for(result: DpaResult) -> int:
    return {"PASS": 0, "REVISE": 1, "BLOCK": 2}[result.conclusion]
