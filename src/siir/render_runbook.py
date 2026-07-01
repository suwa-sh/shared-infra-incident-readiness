"""Render an incident initial-response runbook (deterministic, not generative).

Given an organisation's responsibility-matrix answers and a scenario id, this
lays out the three-stage structure the source article prescribes — 責任境界表 →
Runbook → Communication Tree — by mechanically expanding the canonical
definitions. No free-form LLM generation: the same inputs always produce the
same Markdown, so the output is reviewable and diffable.
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
class RunbookModel:
    target: str
    scenario: dict
    stage1_items: list[dict] = field(default_factory=list)
    stage2_activities: list[dict] = field(default_factory=list)
    stage3_branches: list[dict] = field(default_factory=list)


def _role_names(defn: dict, group_key: str = "roles") -> dict[str, str]:
    sep = overlay_mod.separator_of(defn)
    leaves = overlay_mod.group_items(defn).get(group_key, {}).get("leaves", [])
    return {defn_mod.local_id(r["id"], sep): r.get("name", defn_mod.local_id(r["id"], sep)) for r in leaves}


def _effective_cells(item_id: str, item: dict, org_matrix: dict) -> tuple[dict, str]:
    """Org cells if the org filled this item, else the recommended template."""
    org = org_matrix.get(item_id) or {}
    if org:
        return org, "org"
    return item.get("recommended", {}) or {}, "recommended"


def _roles_with(cells: dict, *letters: str) -> list[str]:
    out = []
    for role, v in cells.items():
        if any(n in letters for n in cr._cell_letters(v)):
            out.append(role)
    return out


def _names(role_ids: list[str], names: dict[str, str]) -> list[str]:
    return [names.get(r, r) for r in role_ids]


def build(
    answers_path: str | Path,
    scenario_id: str,
    overlay_paths: list[str | Path] | None = None,
) -> RunbookModel:
    resp = defn_mod.load("responsibility-matrix", overlay_paths=overlay_paths)
    raci = defn_mod.load("incident-raci", overlay_paths=overlay_paths)
    ob_defn = defn_mod.load("notification-obligations", overlay_paths=overlay_paths)
    cl_defn = defn_mod.load("dpa-clauses", overlay_paths=overlay_paths)
    sc_defn = defn_mod.load("scenarios", overlay_paths=overlay_paths)

    resp_sep = overlay_mod.separator_of(resp)
    resp_items = overlay_mod.group_items(resp).get("resp", {}).get("leaves", [])
    raci_sep = overlay_mod.separator_of(raci)
    raci_activities = overlay_mod.group_items(raci).get("raci_act", {}).get("leaves", [])

    ob_sep = overlay_mod.separator_of(ob_defn)
    obligations = {defn_mod.local_id(o["id"], ob_sep): o for o in overlay_mod.group_items(ob_defn).get("obligations", {}).get("leaves", [])}
    cl_sep = overlay_mod.separator_of(cl_defn)
    clauses = {defn_mod.local_id(c["id"], cl_sep): c for c in overlay_mod.group_items(cl_defn).get("clauses", {}).get("leaves", [])}
    sc_sep = overlay_mod.separator_of(sc_defn)
    scenarios = {
        defn_mod.local_id(s["id"], sc_sep): dict(s, id=defn_mod.local_id(s["id"], sc_sep))
        for s in overlay_mod.group_items(sc_defn).get("scenarios", {}).get("leaves", [])
    }

    if scenario_id not in scenarios:
        raise KeyError(f"unknown scenario '{scenario_id}'")
    scenario = scenarios[scenario_id]

    answers = overlay_mod.load_yaml(answers_path) or {}
    org_matrix = answers.get("matrix", {}) or {}
    resp_names = _role_names(resp)
    raci_names = _role_names(raci, "raci_roles")

    # --- Stage 1: responsibility boundary table (effective cells) ---
    item_owner: dict[str, dict] = {}
    for item in resp_items:
        iid = defn_mod.local_id(item["id"], resp_sep)
        cells, source = _effective_cells(iid, item, org_matrix)
        accountable = _names(_roles_with(cells, "A"), resp_names)
        responsible = _names(_roles_with(cells, "R"), resp_names)
        gray = _names(_roles_with(cells, "tbd"), resp_names)
        owner = {
            "id": iid,
            "text": item.get("text", ""),
            "accountable": accountable,
            "responsible": responsible,
            "gray": gray,
            "source": source,
        }
        item_owner[iid] = owner

    focus = set(scenario.get("focus_items", []))
    stage1 = [dict(item_owner[defn_mod.local_id(i["id"], resp_sep)], focus=defn_mod.local_id(i["id"], resp_sep) in focus) for i in resp_items]
    stage2 = _build_stage2(raci_activities, raci_names, obligations, clauses, focus, raci_sep)
    stage3 = _build_stage3(item_owner, obligations)

    return RunbookModel(
        target=answers.get("target", str(answers_path)),
        scenario=scenario,
        stage1_items=stage1,
        stage2_activities=stage2,
        stage3_branches=stage3,
    )


def _cell_has(cell, letter: str) -> bool:
    # "R/A" -> {"R","A"}, "R" -> {"R"}, "-" -> {"-"}
    return letter in str(cell).upper().split("/")


def _activity_sla(act: dict, obligations: dict, clauses: dict) -> str | None:
    if act.get("obligation_ref") in obligations:
        ob = obligations[act["obligation_ref"]]
        return ob.get("duration_text") or (f"{ob.get('duration_hours')}h" if ob.get("duration_hours") else None)
    if act.get("clause_ref") in clauses:
        cl = clauses[act["clause_ref"]]
        return f"{cl.get('sla_hours')}h ({cl.get('title')})" if cl.get("sla_hours") else cl.get("title")
    return None


def _build_stage2(raci_activities: list[dict], names: dict[str, str], obligations: dict, clauses: dict, focus: set, sep: str) -> list[dict]:
    stage2 = []
    for act in raci_activities:
        aid = defn_mod.local_id(act["id"], sep)
        cells = act.get("cells", {})
        stage2.append(
            {
                "id": aid,
                "text": act.get("text", ""),
                "accountable": _names([r for r, v in cells.items() if _cell_has(v, "A")], names),
                "responsible": _names([r for r, v in cells.items() if _cell_has(v, "R")], names),
                "sla": _activity_sla(act, obligations, clauses),
                "focus": aid in focus,
            }
        )
    return stage2


def _build_stage3(item_owner: dict, obligations: dict) -> list[dict]:
    def owner_label(item_id: str) -> str:
        o = item_owner.get(item_id, {})
        acc = ", ".join(o.get("accountable", [])) or "(未割当)"
        res = ", ".join(o.get("responsible", [])) or "-"
        return f"A={acc} / R={res}"

    def ob_text(ob_id: str) -> str:
        return obligations.get(ob_id, {}).get("duration_text", "")

    return [
        {"audience": "利用者 (本人通知)", "ref": "RB01 / OB04", "owner": owner_label("RB01"), "deadline": ob_text("OB04")},
        {"audience": "報道 (プレスリリース)", "ref": "RB04", "owner": owner_label("RB04"), "deadline": "共同 / 個別を Accountable が即決"},
        {"audience": "個情委 (速報→確報)", "ref": "RB02 / OB01・OB02", "owner": owner_label("RB02"), "deadline": f"{ob_text('OB01')} → {ob_text('OB02')}"},
        {"audience": "総務省 (重大事故報告)", "ref": "RB03 / OB03", "owner": owner_label("RB03"), "deadline": ob_text("OB03")},
    ]


def render_text(model: RunbookModel) -> str:
    s = model.scenario
    lines = [
        f"# 初動ランブック: {model.target}",
        "",
        f"- シナリオ: {s.get('title', s.get('id'))}",
        f"- 共有コンポーネント: {s.get('shared_component', '-')}",
        f"- 想定影響ブランド数: {s.get('affected_brands', '-')}",
        "",
        "## Stage 1. 責任境界表 (この事故で誰が何の責任か)",
        "",
        "| 項目 | Accountable | Responsible | 都度協議 | 出典 |",
        "|---|---|---|---|---|",
    ]
    for i in model.stage1_items:
        star = " *" if i.get("focus") else ""
        lines.append(
            f"| {i['id']}{star} {i['text']} | {', '.join(i['accountable']) or '-'} | "
            f"{', '.join(i['responsible']) or '-'} | {', '.join(i['gray']) or '-'} | {i['source']} |"
        )
    lines += ["", "(* = 本シナリオの focus 項目)", "", "## Stage 2. 初動ランブック (Day 0-3 の順序)", ""]
    lines += ["| # | アクティビティ | Accountable | Responsible | SLA |", "|---|---|---|---|---|"]
    for a in model.stage2_activities:
        star = " *" if a.get("focus") else ""
        lines.append(
            f"| {a['id']}{star} | {a['text']} | {', '.join(a['accountable']) or '-'} | "
            f"{', '.join(a['responsible']) or '-'} | {a['sla'] or '-'} |"
        )
    lines += ["", "## Stage 3. Communication Tree (誰がいつ何を言うか)", ""]
    lines += ["| 宛先 | 参照 | 主体 | 期限 |", "|---|---|---|---|"]
    for b in model.stage3_branches:
        lines.append(f"| {b['audience']} | {b['ref']} | {b['owner']} | {b['deadline'] or '-'} |")
    lines.append("")
    return "\n".join(lines)


def render_json(model: RunbookModel) -> str:
    return json.dumps(
        {
            "target": model.target,
            "scenario": model.scenario.get("id"),
            "stage1_responsibility": model.stage1_items,
            "stage2_runbook": model.stage2_activities,
            "stage3_communication_tree": model.stage3_branches,
        },
        indent=2,
        ensure_ascii=False,
    )
