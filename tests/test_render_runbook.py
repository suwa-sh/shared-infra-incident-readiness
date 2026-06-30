import pytest

from siir import render_runbook as rb
from siir import tabletop as tt


def test_runbook_has_three_stages(examples):
    model = rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand")
    assert len(model.stage1_items) == 12
    assert len(model.stage2_activities) == 15
    assert len(model.stage3_branches) == 4
    text = rb.render_text(model)
    assert "Stage 1" in text and "Stage 2" in text and "Stage 3" in text


def test_runbook_is_deterministic(examples):
    a = rb.render_text(rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand"))
    b = rb.render_text(rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand"))
    assert a == b


def test_runbook_resolves_sla_from_obligation(examples):
    model = rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand")
    ac03 = next(a for a in model.stage2_activities if a["id"] == "AC03")  # clause_ref DPA03
    assert ac03["sla"] and "24h" in ac03["sla"]
    ac05 = next(a for a in model.stage2_activities if a["id"] == "AC05")  # obligation_ref OB03
    assert ac05["sla"] == "遅滞なく"


def test_runbook_marks_focus_items(examples):
    model = rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "rce-6brand")
    focus_ids = {i["id"] for i in model.stage1_items if i.get("focus")}
    assert "RB04" in focus_ids


def test_unknown_scenario_raises(examples):
    with pytest.raises(KeyError):
        rb.build(examples / "responsibility" / "sample-oem-mail.yaml", "no-such-scenario")


def test_tabletop_program(examples):
    model = tt.build("rce-6brand", answers_path=examples / "responsibility" / "sample-oem-mail.yaml")
    text = tt.render_text(model)
    assert "Tabletop" in text
    assert model.focus  # focus items resolved
    # RB04 is tbd in the sample, so it should surface a gray role
    rb04 = next((f for f in model.focus if f["ref"] == "RB04"), None)
    assert rb04 is not None
    assert rb04.get("gray")


def test_tabletop_without_answers_uses_recommended(examples):
    model = tt.build("rce-6brand")
    assert model.focus
    assert all(f.get("source") in {"recommended", None} for f in model.focus)
