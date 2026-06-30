import yaml

from siir import check_dpa as cd


def _write(tmp_path, clauses):
    p = tmp_path / "dpa.yaml"
    p.write_text(yaml.safe_dump({"target": "c", "clauses": clauses}, allow_unicode=True), encoding="utf-8")
    return p


def test_all_present_passes(tmp_path):
    clauses = {f"DPA{n:02d}": "present" for n in range(1, 11)}
    result = cd.check(_write(tmp_path, clauses))
    assert result.conclusion == "PASS"
    assert cd.exit_code_for(result) == 0


def test_required_missing_blocks(tmp_path):
    clauses = {f"DPA{n:02d}": "present" for n in range(1, 11)}
    clauses["DPA03"] = "missing"
    result = cd.check(_write(tmp_path, clauses))
    assert result.conclusion == "BLOCK"
    assert cd.exit_code_for(result) == 2


def test_partial_is_revise(tmp_path):
    clauses = {f"DPA{n:02d}": "present" for n in range(1, 11)}
    clauses["DPA05"] = "partial"
    result = cd.check(_write(tmp_path, clauses))
    assert result.conclusion == "REVISE"
    assert cd.exit_code_for(result) == 1


def test_sample_example_blocks(examples):
    result = cd.check(examples / "dpa" / "sample-dpa-answers.yaml")
    assert result.conclusion == "BLOCK"  # DPA03 missing


def test_overlay_added_clause_is_evaluated(tmp_path, examples):
    clauses = {f"DPA{n:02d}": "present" for n in range(1, 11)}
    # DPA11 is added by the overlay and is required -> missing -> BLOCK
    result = cd.check(
        _write(tmp_path, clauses),
        overlay_paths=[examples / "overlays" / "sample-company" / "extra-clauses.yaml"],
    )
    assert any(c.id == "DPA11" for c in result.clauses)
    assert result.conclusion == "BLOCK"
