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
from . import contracts
from . import definitions as defn_mod
from . import input_contracts
import overlay_scoring as overlay_mod

OverlayError = defn_mod.OverlayError


@dataclass
class RunbookModel:
    target: str
    scenario: dict
    stage1_items: list[dict] = field(default_factory=list)
    stage2_activities: list[dict] = field(default_factory=list)
    stage3_branches: list[dict] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


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
    definitions = defn_mod.load_all(overlay_paths)
    resp = definitions["responsibility-matrix"]
    raci = definitions["incident-raci"]
    ob_defn = definitions["notification-obligations"]
    cl_defn = definitions["dpa-clauses"]
    sc_defn = definitions["scenarios"]

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

    answers = input_contracts.load_yaml_answers(
        answers_path, "responsibility-answers.schema.json", "responsibility answers"
    )
    input_contracts.validate_responsibility_semantics(answers, resp)
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
    communication_answers = _mapping_or_empty(
        answers.get("communications"), "answers 'communications'"
    )
    scenario_branches = _list_or_empty(
        scenario.get("communication_branches"), "scenario 'communication_branches'"
    )
    known_communication_ids = _known_communication_branch_ids(scenarios.values())
    stage3 = _build_stage3(
        item_owner,
        obligations,
        scenario_branches,
        communication_answers,
        known_communication_ids,
    )

    return RunbookModel(
        target=answers.get("target", str(answers_path)),
        scenario=scenario,
        stage1_items=stage1,
        stage2_activities=stage2,
        stage3_branches=stage3,
        provenance=contracts.make_provenance(
            "render-runbook",
            definitions=definitions,
            input_paths=[answers_path],
            overlay_paths=overlay_paths,
        ),
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


def _mapping_or_empty(value, label: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _list_or_empty(value, label: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _index_activities(raci_activities: list[dict], sep: str) -> tuple[dict, list[str]]:
    by_id: dict[str, dict] = {}
    ordered_ids: list[str] = []
    for activity in raci_activities:
        aid = defn_mod.local_id(activity["id"], sep)
        if aid in by_id:
            raise ValueError(f"duplicate RACI activity id '{aid}'")
        by_id[aid] = activity
        ordered_ids.append(aid)
    return by_id, ordered_ids


def _activity_graph(by_id: dict, ordered_ids: list[str], sep: str) -> tuple[list[str], dict]:
    roots: list[str] = []
    children: dict[str, list[str]] = {}

    for aid in ordered_ids:
        activity = by_id[aid]
        if "after" not in activity:
            roots.append(aid)
            continue
        after = activity["after"]
        if not isinstance(after, str) or not after.strip():
            raise ValueError(f"RACI activity '{aid}' has a non-string or empty 'after'")
        anchor = defn_mod.local_id(after, sep)
        if anchor not in by_id:
            raise ValueError(f"RACI activity '{aid}' references unknown after '{anchor}'")
        children.setdefault(anchor, []).append(aid)
    return roots, children


def _order_activities(raci_activities: list[dict], sep: str) -> list[dict]:
    """Insert activities carrying ``after`` while preserving definition order.

    Base activities keep their order. Children of the same anchor keep overlay
    order, and a child's descendants follow it. A cycle has no reachable root,
    so the final emitted-count check detects it.
    """
    by_id, ordered_ids = _index_activities(raci_activities, sep)
    roots, children = _activity_graph(by_id, ordered_ids, sep)

    result: list[dict] = []
    emitted: set[str] = set()

    def emit(aid: str) -> None:
        result.append(by_id[aid])
        emitted.add(aid)
        for child in children.get(aid, []):
            emit(child)

    for aid in roots:
        emit(aid)
    if len(emitted) != len(by_id):
        unresolved = next(aid for aid in ordered_ids if aid not in emitted)
        raise ValueError(f"RACI activity after cycle includes '{unresolved}'")
    return result


def _build_stage2(raci_activities: list[dict], names: dict[str, str], obligations: dict, clauses: dict, focus: set, sep: str) -> list[dict]:
    stage2 = []
    for act in _order_activities(raci_activities, sep):
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


def _build_stage3(
    item_owner: dict,
    obligations: dict,
    scenario_branches: list[dict],
    communication_answers: dict,
    known_communication_ids: set[str],
) -> list[dict]:
    def owner_label(item_id: str) -> str:
        o = item_owner.get(item_id, {})
        acc = ", ".join(o.get("accountable", [])) or "(未割当)"
        res = ", ".join(o.get("responsible", [])) or "-"
        return f"A={acc} / R={res}"

    def ob_text(ob_id: str) -> str:
        return obligations.get(ob_id, {}).get("duration_text", "")

    branches = [
        {"audience": "利用者 (本人通知)", "ref": "RB01 / OB04", "owner": owner_label("RB01"), "deadline": ob_text("OB04")},
        {"audience": "報道 (プレスリリース)", "ref": "RB04", "owner": owner_label("RB04"), "deadline": "共同 / 個別を Accountable が即決"},
        {"audience": "個情委 (速報→確報)", "ref": "RB02 / OB01・OB02", "owner": owner_label("RB02"), "deadline": f"{ob_text('OB01')} → {ob_text('OB02')}"},
        {"audience": "総務省 (重大事故報告)", "ref": "RB03 / OB03", "owner": owner_label("RB03"), "deadline": ob_text("OB03")},
    ]
    branch_ids: set[str] = set()
    for branch in scenario_branches:
        branch_id, rendered_branch = _build_scenario_branch(
            branch, item_owner, communication_answers, owner_label
        )
        if branch_id in branch_ids:
            raise ValueError(f"duplicate scenario communication branch id '{branch_id}'")
        branch_ids.add(branch_id)
        branches.append(rendered_branch)
    if known_communication_ids:
        unknown_answer_ids = set(communication_answers) - known_communication_ids
        if unknown_answer_ids:
            unknown = ", ".join(sorted(str(item) for item in unknown_answer_ids))
            raise ValueError(f"unknown communication answer id(s): {unknown}")
    return branches


def _known_communication_branch_ids(scenarios) -> set[str]:
    ids: set[str] = set()
    for scenario in scenarios:
        branches = _list_or_empty(
            scenario.get("communication_branches"),
            f"scenario '{scenario.get('id', '?')}' communication_branches",
        )
        for branch in branches:
            if not isinstance(branch, dict):
                raise ValueError("scenario communication branch must be a mapping")
            branch_id = _string_field(
                branch, "id", "scenario communication branch", required=True
            )
            ids.add(branch_id)
    return ids


def _build_scenario_branch(
    branch, item_owner: dict, communication_answers: dict, owner_label
) -> tuple[str, dict]:
    if not isinstance(branch, dict):
        raise ValueError("scenario communication branch must be a mapping")
    branch_id = _string_field(branch, "id", "scenario communication branch", required=True)
    label = f"communication branch '{branch_id}'"
    answer = _mapping_or_empty(
        communication_answers.get(branch_id), f"communication answer '{branch_id}'"
    )
    responsibility_ref = _string_field(
        branch, "responsibility_ref", label, required=True
    )
    if responsibility_ref not in item_owner:
        raise ValueError(
            f"communication branch '{branch_id}' references unknown responsibility "
            f"'{responsibility_ref}'"
        )
    scenario_deadline = _string_field(branch, "deadline", label)
    answer_deadline = _string_field(
        answer, "deadline", f"communication answer '{branch_id}'"
    )
    return branch_id, {
        "id": branch_id,
        "audience": _string_field(branch, "audience", label) or branch_id,
        "ref": responsibility_ref,
        "owner": owner_label(responsibility_ref),
        "deadline": answer_deadline or scenario_deadline or "未確定 (演習で決定)",
        "trigger": _string_field(branch, "trigger", label),
        "message_boundary": _string_field(branch, "message_boundary", label),
        "source": "org" if answer_deadline else "scenario",
    }


def _string_field(mapping: dict, field: str, label: str, *, required: bool = False) -> str:
    value = mapping.get(field)
    if value is None:
        if required:
            raise ValueError(f"{label} requires a non-empty string '{field}'")
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{label} field '{field}' must be a string")
    return value


def _responsibility_rows(model: RunbookModel) -> list[str]:
    rows = []
    for item in model.stage1_items:
        star = " *" if item.get("focus") else ""
        rows.append(
            f"| {item['id']}{star} {item['text']} | {', '.join(item['accountable']) or '-'} | "
            f"{', '.join(item['responsible']) or '-'} | {', '.join(item['gray']) or '-'} | {item['source']} |"
        )
    return rows


def _activity_rows(model: RunbookModel) -> list[str]:
    rows = []
    for activity in model.stage2_activities:
        star = " *" if activity.get("focus") else ""
        rows.append(
            f"| {activity['id']}{star} | {activity['text']} | "
            f"{', '.join(activity['accountable']) or '-'} | "
            f"{', '.join(activity['responsible']) or '-'} | {activity['sla'] or '-'} |"
        )
    return rows


def _communication_rows(model: RunbookModel) -> list[str]:
    return [
        f"| {branch['audience']} | {branch['ref']} | {branch['owner']} | "
        f"{branch['deadline'] or '-'} | {branch.get('trigger') or '-'} | "
        f"{branch.get('message_boundary') or '-'} |"
        for branch in model.stage3_branches
    ]


def render_text(model: RunbookModel) -> str:
    scenario = model.scenario
    lines = [
        f"# 初動ランブック: {model.target}",
        "",
        f"- シナリオ: {scenario.get('title', scenario.get('id'))}",
        f"- 共有コンポーネント: {scenario.get('shared_component', '-')}",
        f"- 想定影響ブランド数: {scenario.get('affected_brands', '-')}",
        "",
        "## Stage 1. 責任境界表 (この事故で誰が何の責任か)",
        "",
        "| 項目 | Accountable | Responsible | 都度協議 | 出典 |",
        "|---|---|---|---|---|",
    ]
    lines.extend(_responsibility_rows(model))
    lines += ["", "(* = 本シナリオの focus 項目)", "", "## Stage 2. 初動ランブック (Day 0-3 の順序)", ""]
    lines += ["| # | アクティビティ | Accountable | Responsible | SLA |", "|---|---|---|---|---|"]
    lines.extend(_activity_rows(model))
    lines += ["", "## Stage 3. Communication Tree (誰がいつ何を言うか)", ""]
    lines += [
        "| 宛先 | 参照 | 主体 | 期限 | 発火条件 | 伝える範囲 |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(_communication_rows(model))
    lines.append("")
    lines.append(f"<!-- {contracts.render_text_footer(model.provenance)} -->")
    return "\n".join(lines)


def render_json(model: RunbookModel) -> str:
    payload = {
            "target": model.target,
            "scenario": model.scenario.get("id"),
            "stage1_responsibility": model.stage1_items,
            "stage2_runbook": model.stage2_activities,
            "stage3_communication_tree": model.stage3_branches,
        }
    return json.dumps(
        contracts.envelope(payload, model.provenance),
        indent=2,
        ensure_ascii=False,
    )
