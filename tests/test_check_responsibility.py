import pytest
import yaml

from siir import check_responsibility as cr


def _write(tmp_path, matrix, target="t"):
    p = tmp_path / "answers.yaml"
    p.write_text(yaml.safe_dump({"target": target, "matrix": matrix}, allow_unicode=True), encoding="utf-8")
    return p


def _full_ok():
    # every item: exactly one A + at least one R
    return {f"RB{n:02d}": {"principal_isp": "A", "oem_operator": "R"} for n in range(1, 13)}


def test_full_matrix_passes(tmp_path):
    result = cr.check(_write(tmp_path, _full_ok()))
    assert result.conclusion == "PASS"
    assert cr.exit_code_for(result) == 0
    assert result.score == pytest.approx(1.0)


def test_unassigned_item_blocks(tmp_path):
    m = _full_ok()
    m["RB12"] = {}
    result = cr.check(_write(tmp_path, m))
    assert result.conclusion == "BLOCK"
    assert cr.exit_code_for(result) == 2
    rb12 = next(i for i in result.items if i.id == "RB12")
    assert rb12.reason == "unassigned"


def test_tbd_is_revise_not_block(tmp_path):
    m = _full_ok()
    # one item: accountable deferred via tbd, no hard A -> gray zone, not a failure
    m["RB04"] = {"principal_isp": "tbd", "oem_operator": "C"}
    result = cr.check(_write(tmp_path, m))
    assert result.conclusion == "REVISE"
    assert cr.exit_code_for(result) == 1
    rb04 = next(i for i in result.items if i.id == "RB04")
    assert rb04.verdict == "revise"
    assert "oem" not in rb04.gray_roles  # only principal_isp is gray
    assert rb04.gray_roles == ["principal_isp"]


def test_split_accountability_blocks(tmp_path):
    m = _full_ok()
    m["RB01"] = {"principal_isp": "A", "oem_operator": "A", "ops_bpo": "R"}
    result = cr.check(_write(tmp_path, m))
    assert result.conclusion == "BLOCK"
    rb01 = next(i for i in result.items if i.id == "RB01")
    assert rb01.reason == "split_accountability"


def test_sample_oem_mail_example_blocks(examples):
    # ships with RB04=tbd (gray) and RB12 unassigned (block) -> overall BLOCK
    result = cr.check(examples / "responsibility" / "sample-oem-mail.yaml")
    assert result.conclusion == "BLOCK"
    assert any(i.id == "RB12" and i.verdict == "block" for i in result.items)
    assert any(i.id == "RB04" and i.verdict == "revise" for i in result.items)


def test_worked_example_passes(examples):
    result = cr.check(examples / "saas-operator" / "saas-operator-delegation.yaml")
    assert result.conclusion == "PASS"


def test_composite_ra_cell_is_recognized(tmp_path):
    # a role that is both Responsible and Accountable ("R/A") must not be
    # silently dropped to "unassigned"
    m = _full_ok()
    m["RB01"] = {"oem_operator": "R/A"}
    result = cr.check(_write(tmp_path, m))
    rb01 = next(i for i in result.items if i.id == "RB01")
    assert rb01.verdict == "ok"
    assert rb01.count_a == 1
    assert rb01.has_r is True
