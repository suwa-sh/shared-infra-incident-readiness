"""evaluation-containment 公式 overlay と共通描画機能の回帰テスト。"""

import json
from pathlib import Path

import pytest

from siir import (
    check_responsibility,
    cli,
    definitions,
    list_definitions,
    render_runbook,
    tabletop,
)
from siir import check_responsibility as responsibility_scoring


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY_DIR = REPO_ROOT / "overlays" / "evaluation-containment"
RESP_OV = OVERLAY_DIR / "responsibility.yaml"
RACI_OV = OVERLAY_DIR / "incident-raci.yaml"
SCEN_OV = OVERLAY_DIR / "scenarios.yaml"
EVAL_OV = [SCEN_OV, RESP_OV, RACI_OV]
AGENTIC_DIR = REPO_ROOT / "overlays" / "agentic-attacker"
AGENTIC_OV = [
    AGENTIC_DIR / "scenarios.yaml",
    AGENTIC_DIR / "responsibility.yaml",
    AGENTIC_DIR / "incident-raci.yaml",
]
ANSWER_OV = EVAL_OV + [AGENTIC_DIR / "responsibility.yaml"]
ANSWERS = (
    REPO_ROOT / "examples" / "responsibility" / "sample-evaluation-containment.yaml"
)
SAMPLE_COMPANY_OV = (
    REPO_ROOT / "examples" / "overlays" / "sample-company" / "extra-roles.yaml"
)


@pytest.mark.parametrize("path", EVAL_OV, ids=lambda path: path.name)
def test_official_evaluation_overlay_valid(path):
    result = list_definitions.check_overlay(path)
    assert result.ok, [f"{v.path}: {v.message}" for v in result.violations]


def test_responsibility_overlays_score_24_items_with_one_revise():
    result = check_responsibility.check(
        ANSWERS, overlay_paths=[RESP_OV, AGENTIC_DIR / "responsibility.yaml"]
    )
    assert len(result.items) == 24
    verdicts = {item.id: item.verdict for item in result.items}
    assert verdicts["RB36"] == "revise"
    assert [item.id for item in result.items if item.verdict != "ok"] == ["RB36"]
    assert result.conclusion == "REVISE"


def test_responsibility_without_overlay_remains_12_items():
    with pytest.raises(ValueError, match="unknown item"):
        check_responsibility.check(ANSWERS)


def test_evaluation_roles_are_exposed_by_effective_definition():
    summary = next(
        item
        for item in list_definitions.summarize([RESP_OV], detail=True)
        if item["name"] == "shared-infra-responsibility-matrix"
    )
    expected = {
        "evaluation_program_owner",
        "evaluation_operator",
        "evaluation_security_owner",
        "external_harm_owner",
    }
    assert expected <= set(summary["roles"])
    names = {role["id"]: role["name"] for role in summary["role_items"]}
    assert names["evaluation_security_owner"] == "評価セキュリティ責任者"
    rb31 = next(item for item in summary["items"] if item["id"] == "RB31")
    assert "tooling・host・network" in rb31["text"]
    assert rb31["note"]
    assert rb31["recommended"]["evaluation_security_owner"] == "A"


def test_route_overlays_partitions_all_three_files():
    routed = definitions.route_overlays(EVAL_OV)
    assert routed["responsibility-matrix"] == [RESP_OV]
    assert routed["incident-raci"] == [RACI_OV]
    assert routed["scenarios"] == [SCEN_OV]


def test_new_responsibility_rows_use_known_roles_and_strict_raci():
    summaries = list_definitions.summarize([RESP_OV], detail=True)
    summary = next(
        item
        for item in summaries
        if item["name"] == "shared-infra-responsibility-matrix"
    )
    known_roles = set(summary["roles"])
    for item in summary["items"]:
        if not item["id"].startswith("RB3"):
            continue
        cells = item["recommended"]
        letters = [
            letter
            for value in cells.values()
            for letter in responsibility_scoring._cell_letters(value)
        ]
        assert set(cells) <= known_roles
        assert letters.count("A") == 1
        assert letters.count("R") >= 1


def test_new_raci_rows_use_known_roles_and_strict_raci():
    summary = next(
        item
        for item in list_definitions.summarize([RACI_OV], detail=True)
        if item["name"] == "shared-infra-incident-raci"
    )
    known_roles = set(summary["roles"])
    for item in summary["items"]:
        if not item["id"].startswith("AC2"):
            continue
        cells = item["cells"]
        letters = [
            letter
            for value in cells.values()
            for letter in responsibility_scoring._cell_letters(value)
        ]
        assert set(cells) <= known_roles
        assert letters.count("A") == 1
        assert letters.count("R") >= 1


def test_tabletop_focus_resolves_all_evaluation_refs():
    model = tabletop.build("evaluation-containment", ANSWERS, ANSWER_OV)
    focus = {item["ref"]: item for item in model.focus}
    for ref in [f"RB{i}" for i in range(30, 37)] + [f"AC{i}" for i in range(20, 27)]:
        assert focus[ref]["text"]
        assert focus[ref]["owner"]
    assert focus["RB36"]["gray"] == ["第三者対応責任者"]


def test_runbook_orders_containment_and_external_response_chains():
    model = render_runbook.build(ANSWERS, "evaluation-containment", ANSWER_OV)
    ids = [item["id"] for item in model.stage2_activities]
    assert ids.index("AC20") == ids.index("AC02") + 1
    assert ids[ids.index("AC20") : ids.index("AC20") + 4] == [
        "AC20",
        "AC21",
        "AC22",
        "AC23",
    ]
    assert ids[ids.index("AC06") + 1 : ids.index("AC06") + 4] == [
        "AC24",
        "AC25",
        "AC26",
    ]
    assert ids.index("AC23") < ids.index("AC03")


def test_communication_branch_default_and_org_deadline_override(tmp_path):
    default_model = render_runbook.build(ANSWERS, "evaluation-containment", ANSWER_OV)
    default_branch = next(
        item
        for item in default_model.stage3_branches
        if item.get("id") == "affected-third-party"
    )
    assert default_branch["deadline"] == "未確定 (演習で決定)"
    assert default_branch["source"] == "scenario"

    answers = tmp_path / "answers.yaml"
    answers.write_text(
        ANSWERS.read_text(encoding="utf-8")
        + "\ncommunications:\n  affected-third-party:\n    deadline: 検知から30分以内\n",
        encoding="utf-8",
    )
    org_model = render_runbook.build(answers, "evaluation-containment", ANSWER_OV)
    org_branch = next(
        item
        for item in org_model.stage3_branches
        if item.get("id") == "affected-third-party"
    )
    assert org_branch["deadline"] == "検知から30分以内"
    assert org_branch["source"] == "org"
    text = render_runbook.render_text(org_model)
    assert "検知から30分以内" in text
    assert "外部影響が合理的に疑われた時点" in text
    assert "exploit 詳細と保全証拠は自動共有しない" in text
    rendered = json.loads(render_runbook.render_json(org_model))
    assert rendered["contract_version"] == 1
    rendered_branch = rendered["result"]["stage3_communication_tree"][-1]
    assert rendered_branch["deadline"] == "検知から30分以内"
    assert rendered_branch["trigger"] == "外部影響が合理的に疑われた時点"
    assert "exploit 詳細と保全証拠は自動共有しない" in rendered_branch[
        "message_boundary"
    ]


def test_combined_official_overlays_score_24_items_and_load_both_scenarios():
    overlays = EVAL_OV + AGENTIC_OV
    result = check_responsibility.check(
        ANSWERS, overlay_paths=[RESP_OV, AGENTIC_DIR / "responsibility.yaml"]
    )
    assert len(result.items) == 24
    assert [item.id for item in result.items if item.verdict != "ok"] == ["RB36"]
    scenarios = next(
        item
        for item in list_definitions.summarize(overlays)
        if item["name"] == "shared-infra-tabletop-scenarios"
    )
    assert {"evaluation-containment", "agentic-attacker"} <= set(scenarios["ids"])


def test_combined_official_activity_order_is_before_postmortem():
    overlays = EVAL_OV + AGENTIC_OV
    model = render_runbook.build(ANSWERS, "evaluation-containment", overlays)
    ids = [item["id"] for item in model.stage2_activities]
    for activity in [
        "AC16",
        "AC17",
        "AC18",
        "AC20",
        "AC21",
        "AC22",
        "AC23",
        "AC24",
        "AC25",
        "AC26",
    ]:
        assert ids.index(activity) < ids.index("AC15")


def test_three_responsibility_overlays_have_25_effective_items():
    result = check_responsibility.check(
        ANSWERS,
        overlay_paths=[SAMPLE_COMPANY_OV, RESP_OV, AGENTIC_DIR / "responsibility.yaml"],
    )
    assert len(result.items) == 25


def test_activity_order_rejects_unknown_anchor_cycle_and_duplicate():
    with pytest.raises(ValueError, match="unknown after"):
        render_runbook._order_activities(
            [{"id": "raci_act.AC20", "after": "AC99"}], "."
        )
    with pytest.raises(ValueError, match="cycle"):
        render_runbook._order_activities(
            [
                {"id": "raci_act.AC20", "after": "AC21"},
                {"id": "raci_act.AC21", "after": "AC20"},
            ],
            ".",
        )
    with pytest.raises(ValueError, match="duplicate"):
        render_runbook._order_activities(
            [{"id": "raci_act.AC20"}, {"id": "raci_act.AC20"}], "."
        )


@pytest.mark.parametrize("after", [None, "", [], {}, 0])
def test_activity_order_rejects_present_invalid_after(after):
    with pytest.raises(ValueError, match="non-string or empty"):
        render_runbook._order_activities(
            [{"id": "raci_act.AC20", "after": after}], "."
        )


def test_cli_detail_requires_json_format():
    assert cli.main(["list-definitions", "--detail"]) == 3


def test_cli_scenario_only_rejects_unresolved_responsibility_ref():
    assert (
        cli.main(
            [
                "render-runbook",
                str(ANSWERS),
                "--scenario",
                "evaluation-containment",
                "--overlay",
                str(SCEN_OV),
            ]
        )
        == 3
    )


def test_cli_rejects_unknown_communication_answer_id(tmp_path):
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        ANSWERS.read_text(encoding="utf-8")
        + "\ncommunications:\n  affected_third_party:\n    deadline: 30分以内\n",
        encoding="utf-8",
    )
    argv = [
        "render-runbook",
        str(answers),
        "--scenario",
        "evaluation-containment",
    ]
    for overlay in ANSWER_OV:
        argv += ["--overlay", str(overlay)]
    assert cli.main(argv) == 3


def test_cli_rejects_falsy_non_mapping_communications(tmp_path):
    answers = tmp_path / "answers.yaml"
    answers.write_text("target: bad\ncommunications: []\n", encoding="utf-8")
    argv = [
        "render-runbook",
        str(answers),
        "--scenario",
        "evaluation-containment",
    ]
    for overlay in ANSWER_OV:
        argv += ["--overlay", str(overlay)]
    assert cli.main(argv) == 3


@pytest.mark.parametrize(
    "branch_lines",
    [
        ["        id: [bad]", "        responsibility_ref: RB01"],
        ["        id: bad", "        responsibility_ref: RB01", "        deadline: [30m]"],
        ["        id: bad", "        responsibility_ref: RB01", "        trigger: [bad]"],
    ],
    ids=["list-id", "list-deadline", "list-trigger"],
)
def test_cli_rejects_invalid_communication_branch_field_types(tmp_path, branch_lines):
    overlay = tmp_path / "scenario.yaml"
    lines = [
        "extends: shared-infra-tabletop-scenarios",
        "add:",
        "  - id: scenarios.bad-communication",
        "    title: bad communication",
        "    communication_branches:",
        "      -",
        *branch_lines,
    ]
    overlay.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert (
        cli.main(
            [
                "render-runbook",
                str(ANSWERS),
                "--scenario",
                "bad-communication",
                "--overlay",
                str(overlay),
            ]
        )
        == 3
    )


def test_cli_rejects_non_string_answer_deadline(tmp_path):
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        ANSWERS.read_text(encoding="utf-8")
        + "\ncommunications:\n  affected-third-party:\n    deadline: [30m]\n",
        encoding="utf-8",
    )
    argv = [
        "render-runbook",
        str(answers),
        "--scenario",
        "evaluation-containment",
    ]
    for overlay in ANSWER_OV:
        argv += ["--overlay", str(overlay)]
    assert cli.main(argv) == 3


def test_answers_can_store_deadlines_for_multiple_loaded_scenarios(tmp_path):
    second_scenario = tmp_path / "second-scenario.yaml"
    second_scenario.write_text(
        "extends: shared-infra-tabletop-scenarios\n"
        "add:\n"
        "  - id: scenarios.second-communication\n"
        "    title: second communication\n"
        "    communication_branches:\n"
        "      - id: second-party\n"
        "        audience: 別の連絡先\n"
        "        responsibility_ref: RB01\n",
        encoding="utf-8",
    )
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        ANSWERS.read_text(encoding="utf-8")
        + "\ncommunications:\n"
        + "  affected-third-party:\n    deadline: 30分以内\n"
        + "  second-party:\n    deadline: 60分以内\n",
        encoding="utf-8",
    )
    overlays = ANSWER_OV + [second_scenario]
    evaluation = render_runbook.build(
        answers, "evaluation-containment", overlay_paths=overlays
    )
    second = render_runbook.build(
        answers, "second-communication", overlay_paths=overlays
    )
    evaluation_branch = next(
        item
        for item in evaluation.stage3_branches
        if item.get("id") == "affected-third-party"
    )
    second_branch = next(
        item for item in second.stage3_branches if item.get("id") == "second-party"
    )
    assert evaluation_branch["deadline"] == "30分以内"
    assert second_branch["deadline"] == "60分以内"
