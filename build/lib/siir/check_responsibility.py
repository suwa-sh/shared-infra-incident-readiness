"""Score an organisation's filled responsibility-boundary matrix.

Input answers YAML::

    target: <org / platform name>
    matrix:
      RB01: { principal_isp: R, oem_operator: C, ops_bpo: I, sw_vendor: I }
      RB02: { principal_isp: A, oem_operator: tbd }
      RB12: {}              # completely unassigned

For each definition item we evaluate the org's cells for RACI soundness:

- exactly one Accountable (A), at least one Responsible (R) => ok
- an explicit ``tbd`` / ``negotiate`` box is a *gray zone*, surfaced as a
  warning (REVISE) — never a hard failure. The source article is explicit that
  leaving a "不明 / 都度協議" box is a deliberate, healthy practice, so a blank
  that the org consciously marked tbd must not be punished like a true gap.
- a completely blank item, a missing A with no tbd, or a split A => BLOCK.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import definitions as defn_mod
import overlay_scoring as overlay_mod

OverlayError = defn_mod.OverlayError

_LETTERS = {"R", "A", "C", "I"}
_GRAY = {"tbd", "negotiate"}


@dataclass
class ItemResult:
    id: str
    text: str
    verdict: str  # ok | revise | block
    reason: str
    count_a: int
    has_r: bool
    gray_roles: list[str] = field(default_factory=list)


@dataclass
class ResponsibilityResult:
    target: str
    items: list[ItemResult]
    conclusion: str  # PASS | REVISE | BLOCK

    @property
    def score(self) -> float:
        if not self.items:
            return 0.0
        ok = sum(1 for i in self.items if i.verdict == "ok")
        return ok / len(self.items)


def _normalize(value: Any) -> str | None:
    """Map a single cell token to R/A/C/I, 'tbd', or None (n/a / blank)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    up = s.upper()
    if up in _LETTERS:
        return up
    low = s.lower()
    if low in _GRAY:
        return "tbd"
    return None


def _cell_letters(value: Any) -> list[str]:
    """Split a possibly-composite cell ("R/A") into normalized tokens.

    A role that is both Responsible and Accountable is written ``R/A`` in the
    incident-raci style; a plain matrix uses single letters. Splitting on '/'
    keeps both representations working so a "R/A" answer is not silently
    dropped to "unassigned".
    """
    if value is None:
        return []
    out: list[str] = []
    for tok in str(value).split("/"):
        n = _normalize(tok)
        if n:
            out.append(n)
    return out


def _verdict_for(cells: dict) -> tuple[str, str, int, bool, list[str]]:
    """Judge a row's ownership clarity.

    The source article's own template often marks the primary owner with a
    single ``R`` and no separate ``A`` (rows 1, 5, 6, 8, 9, 10), so requiring a
    distinct ``A`` everywhere would contradict it. The real failures are: no one
    assigned, split accountability (two A), or genuinely ambiguous ownership
    (two R and no A). An explicit ``tbd`` is a gray zone (REVISE), never a block.
    """
    gray_roles = [role for role, v in cells.items() if "tbd" in _cell_letters(v)]
    assigned = [n for v in cells.values() for n in _cell_letters(v) if n in _LETTERS]
    count_a = assigned.count("A")
    r_count = assigned.count("R")
    has_r = r_count > 0
    has_gray = bool(gray_roles)

    if not assigned and not has_gray:
        return "block", "unassigned", count_a, has_r, gray_roles
    if count_a > 1:
        return "block", "split_accountability", count_a, has_r, gray_roles
    if count_a == 1:
        verdict = "revise" if has_gray else "ok"
        return verdict, ("gray_zone" if has_gray else "ok"), count_a, has_r, gray_roles
    # count_a == 0: rely on a single clear Responsible owner
    if r_count == 1:
        verdict = "revise" if has_gray else "ok"
        return verdict, ("gray_zone" if has_gray else "ok"), count_a, has_r, gray_roles
    if r_count > 1:
        return "revise", "ambiguous_ownership", count_a, has_r, gray_roles
    # no A, no R
    if has_gray:
        return "revise", "accountability_deferred", count_a, has_r, gray_roles
    return "block", "no_owner", count_a, has_r, gray_roles


def check(
    answers_path: str | Path,
    overlay_paths: list[str | Path] | None = None,
    definition_path_override: str | Path | None = None,
) -> ResponsibilityResult:
    defn = defn_mod.load(
        "responsibility-matrix",
        overlay_paths=overlay_paths,
        definition_path_override=definition_path_override,
    )
    answers = overlay_mod.load_yaml(answers_path) or {}
    matrix = answers.get("matrix", {}) or {}

    sep = overlay_mod.separator_of(defn)
    resp_leaves = overlay_mod.group_items(defn).get("resp", {}).get("leaves", [])

    items: list[ItemResult] = []
    for item in resp_leaves:
        iid = defn_mod.local_id(item["id"], sep)
        cells = matrix.get(iid, {}) or {}
        verdict, reason, count_a, has_r, gray = _verdict_for(cells)
        items.append(
            ItemResult(
                id=iid,
                text=item.get("text", ""),
                verdict=verdict,
                reason=reason,
                count_a=count_a,
                has_r=has_r,
                gray_roles=gray,
            )
        )

    verdicts = {i.verdict for i in items}
    if "block" in verdicts:
        conclusion = "BLOCK"
    elif "revise" in verdicts:
        conclusion = "REVISE"
    else:
        conclusion = "PASS"

    return ResponsibilityResult(
        target=answers.get("target", str(answers_path)),
        items=items,
        conclusion=conclusion,
    )


_MARK = {"ok": "[OK]", "revise": "[..]", "block": "[NG]"}


def render_text(result: ResponsibilityResult) -> str:
    lines = [f"Target: {result.target}", f"Responsibility readiness: {int(result.score * 100)}%", ""]
    for i in result.items:
        lines.append(f"{_MARK.get(i.verdict, '[??]')} {i.id} {i.text}: {i.verdict.upper()} ({i.reason})")
        if i.gray_roles:
            lines.append(f"    gray (tbd): {', '.join(i.gray_roles)}")
    lines.append("")
    lines.append(f"Conclusion: {result.conclusion}")
    return "\n".join(lines)


def render_json(result: ResponsibilityResult) -> str:
    return json.dumps(
        {
            "target": result.target,
            "conclusion": result.conclusion,
            "score": result.score,
            "items": [
                {
                    "id": i.id,
                    "text": i.text,
                    "verdict": i.verdict,
                    "reason": i.reason,
                    "count_a": i.count_a,
                    "has_r": i.has_r,
                    "gray_roles": i.gray_roles,
                }
                for i in result.items
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def exit_code_for(result: ResponsibilityResult) -> int:
    return {"PASS": 0, "REVISE": 1, "BLOCK": 2}[result.conclusion]
