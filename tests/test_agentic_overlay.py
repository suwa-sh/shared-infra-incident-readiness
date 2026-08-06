"""agentic-attacker 公式 overlay (overlays/agentic-attacker/) の回帰テスト。

3 ファイルの overlay 妥当性、check-responsibility の 17 項目採点、
route_overlays による複数定義コマンド (tabletop / render-runbook /
list-definitions) への振り分け、単一定義コマンドの不一致エラーを固定する。
"""

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

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY_DIR = REPO_ROOT / "overlays" / "agentic-attacker"
RESP_OV = OVERLAY_DIR / "responsibility.yaml"
RACI_OV = OVERLAY_DIR / "incident-raci.yaml"
SCEN_OV = OVERLAY_DIR / "scenarios.yaml"
ALL_OV = [SCEN_OV, RESP_OV, RACI_OV]
ANSWERS = REPO_ROOT / "examples" / "responsibility" / "sample-agentic.yaml"
SAMPLE_COMPANY_ROLES_OV = REPO_ROOT / "examples" / "overlays" / "sample-company" / "extra-roles.yaml"


# --- overlay 妥当性 ---


@pytest.mark.parametrize("path", ALL_OV, ids=lambda p: p.name)
def test_official_overlay_valid_merges_ok(path):
    result = list_definitions.check_overlay(path)
    assert result.ok, [f"{v.path}: {v.message}" for v in result.violations]


# --- check-responsibility (単一定義コマンド) ---


def test_check_responsibility_with_overlay_scores_17_items_revise():
    result = check_responsibility.check(ANSWERS, overlay_paths=[RESP_OV])
    assert len(result.items) == 17
    by_id = {i.id: i for i in result.items}
    assert by_id["RB21"].verdict == "revise"          # 主権基盤の owner が tbd → gray
    ok_count = sum(1 for i in result.items if i.verdict == "ok")
    assert ok_count == 16
    assert result.conclusion == "REVISE"


def test_check_responsibility_without_overlay_unchanged_12_items():
    result = check_responsibility.check(ANSWERS)
    assert len(result.items) == 12                    # overlay 無しでは既存診断のまま


def test_check_responsibility_mismatched_overlay_raises():
    with pytest.raises(definitions.OverlayError):
        check_responsibility.check(ANSWERS, overlay_paths=[SCEN_OV])


# --- route_overlays ---


def test_route_overlays_partitions_by_extends():
    routed = definitions.route_overlays(ALL_OV)
    assert routed["scenarios"] == [SCEN_OV]
    assert routed["responsibility-matrix"] == [RESP_OV]
    assert routed["incident-raci"] == [RACI_OV]
    assert routed["dpa-clauses"] == []


def test_route_overlays_unknown_extends_raises(tmp_path):
    bogus = tmp_path / "bogus.yaml"
    bogus.write_text("extends: no-such-definition\nadd: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        definitions.route_overlays([bogus])


# --- 複数定義コマンド (build 層) ---


def test_tabletop_build_with_all_overlays_resolves_scenario_and_focus():
    model = tabletop.build("agentic-attacker", answers_path=ANSWERS, overlay_paths=ALL_OV)
    assert model.scenario["id"] == "agentic-attacker"
    focus_by_ref = {f["ref"]: f for f in model.focus}
    for ref in ["RB20", "RB21", "RB22", "RB23", "RB24", "RB06"]:
        assert focus_by_ref[ref]["text"], f"focus {ref} should resolve against the overlaid matrix"
    assert focus_by_ref["RB21"]["gray"], "RB21 の tbd が演習の焦点として出ること"


def test_tabletop_focus_resolves_raci_activity_refs():
    model = tabletop.build("agentic-attacker", answers_path=ANSWERS, overlay_paths=ALL_OV)
    focus_by_ref = {f["ref"]: f for f in model.focus}
    for ref in ["AC16", "AC17", "AC18"]:
        assert focus_by_ref[ref]["text"], f"AC ref {ref} は incident-raci から本文を解決すること"
        assert focus_by_ref[ref]["source"] == "raci"
        assert focus_by_ref[ref]["owner"], f"AC ref {ref} は担当 (A) を解決すること"


def test_tabletop_sole_responsible_shown_as_owner_not_unassigned():
    # check-responsibility は「A 無し・単独 R」を ok とするので、演習も未割当と表示しない
    model = tabletop.build("agentic-attacker", answers_path=ANSWERS, overlay_paths=ALL_OV)
    focus_by_ref = {f["ref"]: f for f in model.focus}
    for ref in ["RB05", "RB08"]:  # sample-agentic では oem_operator: R の単独 R
        assert "未割当" not in focus_by_ref[ref]["owner"]
        assert "(R)" in focus_by_ref[ref]["owner"]


def test_render_runbook_with_all_overlays_includes_added_activities():
    model = render_runbook.build(ANSWERS, "agentic-attacker", overlay_paths=ALL_OV)
    stage2_ids = [a["id"] for a in model.stage2_activities]
    assert {"AC16", "AC17", "AC18"} <= set(stage2_ids)
    stage1_ids = [i["id"] for i in model.stage1_items]
    assert {"RB20", "RB21", "RB22", "RB23", "RB24"} <= set(stage1_ids)


def test_list_definitions_with_all_overlays_reflects_merge():
    summaries = {s["name"]: s for s in list_definitions.summarize(overlay_paths=ALL_OV)}
    assert summaries["shared-infra-responsibility-matrix"]["count"] == 17
    assert "agentic-attacker" in summaries["shared-infra-tabletop-scenarios"]["ids"]
    assert "AC18" in summaries["shared-infra-incident-raci"]["ids"]


# --- 併用回帰 (sample-company overlay と同時適用) ---


def test_responsibility_overlay_coexists_with_sample_company_overlay():
    result = check_responsibility.check(
        ANSWERS, overlay_paths=[SAMPLE_COMPANY_ROLES_OV, RESP_OV]
    )
    assert len(result.items) == 18                    # 12 + RB13 (sample) + RB20-24


# --- CLI 層 (argparse を通す exit code 契約) ---


def _run(argv) -> int:
    return cli.main(argv)


def test_cli_tabletop_with_three_overlays_exits_0():
    assert (
        _run(
            [
                "tabletop",
                "--scenario",
                "agentic-attacker",
                str(ANSWERS),
                "--overlay",
                str(SCEN_OV),
                "--overlay",
                str(RESP_OV),
                "--overlay",
                str(RACI_OV),
            ]
        )
        == 0
    )


def test_cli_check_responsibility_with_overlay_exits_1_revise():
    assert (
        _run(["check-responsibility", str(ANSWERS), "--overlay", str(RESP_OV)]) == 1
    )


def test_cli_check_responsibility_mismatched_overlay_exits_3():
    assert (
        _run(["check-responsibility", str(ANSWERS), "--overlay", str(SCEN_OV)]) == 3
    )


def test_cli_list_definitions_unknown_extends_exits_3(tmp_path):
    bogus = tmp_path / "bogus.yaml"
    bogus.write_text("extends: no-such-definition\nadd: []\n", encoding="utf-8")
    assert _run(["list-definitions", "--overlay", str(bogus)]) == 3


@pytest.mark.parametrize(
    "argv_head",
    [
        ["list-definitions"],
        ["tabletop", "--scenario", "rce-6brand"],
        ["render-runbook", "REPLACE_ANSWERS", "--scenario", "rce-6brand"],
        ["check-responsibility", "REPLACE_ANSWERS"],
    ],
    ids=["list-definitions", "tabletop", "render-runbook", "check-responsibility"],
)
def test_cli_non_mapping_overlay_exits_3(tmp_path, argv_head):
    # トップレベルが list の overlay は構造エラー (exit 3)。AttributeError で
    # exit 1 に漏れない (レビュー指摘: 全 overlay 読込経路の mapping 検証)
    bad = tmp_path / "bad-list.yaml"
    bad.write_text("- not-a-mapping\n", encoding="utf-8")
    argv = [str(ANSWERS) if a == "REPLACE_ANSWERS" else a for a in argv_head]
    assert _run(argv + ["--overlay", str(bad)]) == 3


def test_cli_check_overlay_non_mapping_exits_3(tmp_path):
    bad = tmp_path / "bad-list.yaml"
    bad.write_text("- not-a-mapping\n", encoding="utf-8")
    assert _run(["check-overlay", str(bad)]) == 3


def test_tabletop_ac_sole_responsible_shown_as_owner(tmp_path):
    # 正本 AC11 (フォレンジック開始) は oem_operator: R のみで A 無し。
    # RB と同じ resolver で「<role> (R)」表示になること (未割当と出さない)
    ov = tmp_path / "focus-ac11.yaml"
    ov.write_text(
        "extends: shared-infra-tabletop-scenarios\n"
        "add:\n"
        "  - id: scenarios.ac11-drill\n"
        "    title: AC11 drill\n"
        "    focus_items: [AC11]\n",
        encoding="utf-8",
    )
    model = tabletop.build("ac11-drill", overlay_paths=[ov])
    (ac11,) = model.focus
    assert ac11["text"]
    assert "(R)" in ac11["owner"]
    assert "未割当" not in ac11["owner"]
