"""Lock the CLI exit-code contract (0 ok / 1 partial / 2 block / 3 input error)
through the real argparse wrapper — the unit tests alone did not catch argparse
and YAML-parse paths leaking exit 2 / 1."""

from pathlib import Path

import pytest

from siir import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EX = REPO_ROOT / "examples"


def run(argv) -> int:
    return cli.main(argv)


def test_check_responsibility_block_exits_2():
    assert run(["check-responsibility", str(EX / "responsibility" / "sample-oem-mail.yaml")]) == 2


def test_check_responsibility_pass_exits_0():
    assert run(["check-responsibility", str(EX / "saas-operator" / "saas-operator-delegation.yaml")]) == 0


def test_check_dpa_block_exits_2():
    assert run(["check-dpa", str(EX / "dpa" / "sample-dpa-answers.yaml")]) == 2


def test_validate_record_block_exits_2():
    assert run(["validate-record", str(EX / "records" / "sample-incident.json"), "--level", "extended"]) == 2


def test_render_runbook_exits_0():
    assert run(["render-runbook", str(EX / "responsibility" / "sample-oem-mail.yaml"), "--scenario", "rce-6brand"]) == 0


def test_tabletop_exits_0():
    assert run(["tabletop", "--scenario", "rce-6brand", str(EX / "responsibility" / "sample-oem-mail.yaml")]) == 0


def test_check_overlay_ok_exits_0():
    assert run(["check-overlay", str(EX / "overlays" / "sample-company" / "extra-clauses.yaml")]) == 0


def test_check_overlay_bad_exits_2(tmp_path):
    bad = tmp_path / "bad-overlay.yaml"
    bad.write_text("extends: shared-infra-dpa-clauses\nadd:\n  clauses:\n    - id: DPA01\n", encoding="utf-8")
    assert run(["check-overlay", str(bad)]) == 2  # id collision -> rejected overlay


def test_missing_file_exits_3():
    assert run(["check-dpa", "/no/such/file.yaml"]) == 3


def test_bad_yaml_exits_3(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("target: x\nmatrix: [unclosed\n", encoding="utf-8")
    assert run(["check-responsibility", str(bad)]) == 3


def test_unknown_subcommand_exits_3():
    with pytest.raises(SystemExit) as e:
        run(["no-such-command"])
    assert e.value.code == 3


def test_bad_flag_exits_3():
    with pytest.raises(SystemExit) as e:
        run(["check-dpa", "--no-such-flag", "x.yaml"])
    assert e.value.code == 3
