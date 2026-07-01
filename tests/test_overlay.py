"""Tests for the canonical overlay engine (flat items, add / strengthen)."""

from siir import definitions as defn_mod
from siir import overlay as ov


def _base(name):
    return defn_mod.load(name)


def _ids(defn):
    return [i["id"] for i in defn["items"]]


def test_base_definitions_validate():
    for name in defn_mod.DEFINITION_FILES:
        assert ov.validate_definition(_base(name)) == []


def test_add_role_and_item_ok(examples):
    base = _base("responsibility-matrix")
    overlay = ov.load_yaml(examples / "overlays" / "sample-company" / "extra-roles.yaml")
    result = ov.apply_overlay(base, overlay)
    assert result.ok, [v.message for v in result.violations]
    ids = _ids(result.merged)
    assert "roles.end_user" in ids
    assert "resp.RB13" in ids


def test_strengthen_lower_ok_and_weaken_rejected(examples):
    base = _base("dpa-clauses")
    overlay = ov.load_yaml(examples / "overlays" / "sample-company" / "extra-clauses.yaml")
    result = ov.apply_overlay(base, overlay)
    assert result.ok, [v.message for v in result.violations]
    dpa03 = next(i for i in result.merged["items"] if i["id"] == "clauses.DPA03")
    assert dpa03["sla_hours"] == 12  # 24 -> 12 is stricter
    assert dpa03["sla_confirmed_hours"] == 72  # untouched

    # weakening (12 -> 48 relative to base 24) must be rejected
    weaken = {"extends": "shared-infra-dpa-clauses", "strengthen": {"clauses.DPA03": {"sla_hours": 48}}}
    bad = ov.apply_overlay(base, weaken)
    assert not bad.ok
    assert any(v.kind == "weakening_rejected" for v in bad.violations)


def test_strengthen_confirmed_sla_lower_is_accepted():
    # the 72h confirmed-report SLA is independently strengthen-able
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "strengthen": {"clauses.DPA03": {"sla_confirmed_hours": 48}}}
    result = ov.apply_overlay(base, overlay)
    assert result.ok, [v.message for v in result.violations]
    dpa03 = next(i for i in result.merged["items"] if i["id"] == "clauses.DPA03")
    assert dpa03["sla_confirmed_hours"] == 48
    assert dpa03["sla_hours"] == 24  # untouched


def test_add_collision_rejected():
    base = _base("dpa-clauses")
    overlay = {
        "extends": "shared-infra-dpa-clauses",
        "add": [{"id": "clauses.DPA01", "title": "dup"}],
    }
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "id_collision" for v in result.violations)


def test_add_unknown_group_is_rejected():
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "add": [{"id": "bogus.DPAX", "title": "x"}]}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "unsupported_op" for v in result.violations)


def test_unknown_extension_point_rejected():
    # responsibility-matrix declares add for roles/resp only; strengthen has no targets
    base = _base("responsibility-matrix")
    overlay = {"extends": "shared-infra-responsibility-matrix", "strengthen": {"resp.RB01": {"weight": 2}}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "unsupported_op" for v in result.violations)


def test_extends_mismatch_rejected():
    base = _base("dpa-clauses")
    overlay = {"extends": "wrong-name", "add": [{"id": "clauses.DPAX"}]}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "extends_mismatch" for v in result.violations)


def test_unknown_top_level_key_rejected():
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "replace": []}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "unsupported_op" for v in result.violations)


def test_strengthen_non_numeric_rejected_even_when_base_absent():
    # DPA01 has no sla_hours (base None); a non-numeric strengthen must still be
    # rejected rather than slipping into a declared-numeric field
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "strengthen": {"clauses.DPA01": {"sla_hours": "soon"}}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "invalid_overlay" for v in result.violations)


def test_group_items_preserves_source_order():
    defn = _base("responsibility-matrix")
    groups = ov.group_items(defn)
    assert list(groups.keys()) == ["roles", "resp"]
    role_ids = [i["id"] for i in groups["roles"]["leaves"]]
    assert role_ids == ["roles.principal_isp", "roles.oem_operator", "roles.ops_bpo", "roles.sw_vendor"]
    resp_ids = [i["id"] for i in groups["resp"]["leaves"]]
    assert resp_ids[0] == "resp.RB01" and resp_ids[-1] == "resp.RB12"
