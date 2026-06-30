"""Render a Tabletop exercise facilitation program (deterministic).

Expands a machine-readable scenario (scenarios.yaml) into a facilitator's
program: overview, timed injects, facilitation questions, and the focus items
to drill. If an organisation's responsibility-matrix answers are supplied, the
focus items are annotated with who is Accountable/Responsible so the exercise
drills the org's *actual* table rather than a generic one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import check_responsibility as cr
from . import definitions as defn_mod
from . import overlay as overlay_mod

OverlayError = defn_mod.OverlayError


@dataclass
class TabletopModel:
    scenario: dict
    focus: list[dict] = field(default_factory=list)
    target: str | None = None


def build(
    scenario_id: str,
    answers_path: str | Path | None = None,
    overlay_paths: list[str | Path] | None = None,
) -> TabletopModel:
    scenarios = {s["id"]: s for s in defn_mod.load("scenarios", overlay_paths=overlay_paths).get("scenarios", [])}
    if scenario_id not in scenarios:
        raise KeyError(f"unknown scenario '{scenario_id}'")
    scenario = scenarios[scenario_id]

    resp = defn_mod.load("responsibility-matrix", overlay_paths=overlay_paths)
    item_by_id = {i["id"]: i for i in resp["items"]}
    role_names = {r["id"]: r.get("name", r["id"]) for r in resp.get("roles", [])}

    org_matrix = {}
    target = None
    if answers_path:
        answers = overlay_mod.load_yaml(answers_path) or {}
        org_matrix = answers.get("matrix", {}) or {}
        target = answers.get("target")

    focus = []
    for ref in scenario.get("focus_items", []):
        if not ref.startswith("RB") or ref not in item_by_id:
            focus.append({"ref": ref, "text": "", "owner": None})
            continue
        item = item_by_id[ref]
        cells = org_matrix.get(ref) or item.get("recommended", {}) or {}
        acc = [role_names.get(r, r) for r, v in cells.items() if "A" in cr._cell_letters(v)]
        gray = [role_names.get(r, r) for r, v in cells.items() if "tbd" in cr._cell_letters(v)]
        focus.append(
            {
                "ref": ref,
                "text": item.get("text", ""),
                "owner": ", ".join(acc) or "(未割当 — 演習で確定する)",
                "gray": gray,
                "source": "org" if org_matrix.get(ref) else "recommended",
            }
        )

    return TabletopModel(scenario=scenario, focus=focus, target=target)


def render_text(model: TabletopModel) -> str:
    s = model.scenario
    lines = [
        f"# Tabletop 演習プログラム: {s.get('title', s.get('id'))}",
        "",
        f"- 共有コンポーネント: {s.get('shared_component', '-')}",
        f"- 想定影響ブランド数: {s.get('affected_brands', '-')}",
        f"- 所要時間: {s.get('duration_minutes', '-')} 分",
    ]
    if model.target:
        lines.append(f"- 対象組織: {model.target}")
    lines += ["", f"トリガー: {s.get('trigger', '-')}", "", "## 注入イベント (時系列)", ""]
    for inj in s.get("injects", []):
        lines.append(f"- T+{inj.get('at_minute', '?')}分: {inj.get('event', '')}")
    lines += ["", "## ファシリテーション設問", ""]
    for i, q in enumerate(s.get("facilitation_questions", []), 1):
        lines.append(f"{i}. {q}")
    lines += ["", "## focus 項目 (この演習で叩く責任境界)", ""]
    lines += ["| 項目 | 内容 | Accountable | 都度協議 | 出典 |", "|---|---|---|---|---|"]
    for f in model.focus:
        gray = ", ".join(f.get("gray", []) or []) or "-"
        lines.append(f"| {f['ref']} | {f.get('text', '')} | {f.get('owner') or '-'} | {gray} | {f.get('source', '-')} |")
    lines.append("")
    return "\n".join(lines)


def render_json(model: TabletopModel) -> str:
    return json.dumps(
        {
            "scenario": model.scenario.get("id"),
            "title": model.scenario.get("title"),
            "target": model.target,
            "injects": model.scenario.get("injects", []),
            "facilitation_questions": model.scenario.get("facilitation_questions", []),
            "focus": model.focus,
        },
        indent=2,
        ensure_ascii=False,
    )
