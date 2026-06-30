from siir import definitions as defn_mod
from siir import overlay as ov


def _base(name):
    return defn_mod.load(name)


def test_add_role_and_item_ok(examples):
    base = _base("responsibility-matrix")
    overlay = ov.load_yaml(examples / "overlays" / "sample-company" / "extra-roles.yaml")
    result = ov.apply_overlay(base, overlay)
    assert result.ok, [v.message for v in result.violations]
    role_ids = {r["id"] for r in result.merged["roles"]}
    item_ids = {i["id"] for i in result.merged["items"]}
    assert "end_user" in role_ids
    assert "RB13" in item_ids


def test_strengthen_lower_ok_and_weaken_rejected(examples):
    base = _base("dpa-clauses")
    overlay = ov.load_yaml(examples / "overlays" / "sample-company" / "extra-clauses.yaml")
    result = ov.apply_overlay(base, overlay)
    assert result.ok, [v.message for v in result.violations]
    dpa03 = next(c for c in result.merged["clauses"] if c["id"] == "DPA03")
    assert dpa03["sla_hours"] == 12  # 24 -> 12 is stricter

    # weakening (12 -> 48 relative to base 24) must be rejected
    weaken = {"extends": "shared-infra-dpa-clauses", "strengthen": {"clauses": {"DPA03": {"sla_hours": 48}}}}
    bad = ov.apply_overlay(base, weaken)
    assert not bad.ok
    assert any(v.kind == "weakening_rejected" for v in bad.violations)


def test_add_collision_rejected():
    base = _base("dpa-clauses")
    overlay = {
        "extends": "shared-infra-dpa-clauses",
        "add": {"clauses": [{"id": "DPA01", "title": "dup"}]},
    }
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "id_collision" for v in result.violations)


def test_unknown_extension_point_rejected():
    base = _base("responsibility-matrix")
    # responsibility-matrix declares add for roles/items only; strengthen has no targets
    overlay = {"extends": "shared-infra-responsibility-matrix", "strengthen": {"items": {"RB01": {"weight": 2}}}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "unsupported_op" for v in result.violations)


def test_extends_mismatch_rejected():
    base = _base("dpa-clauses")
    overlay = {"extends": "wrong-name", "add": {"clauses": [{"id": "DPAX"}]}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "extends_mismatch" for v in result.violations)


def test_unknown_top_level_key_rejected():
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "replace": {"clauses": []}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "unsupported_op" for v in result.violations)


def test_strengthen_non_numeric_rejected_even_when_base_absent():
    # DPA01 has no sla_hours (base None); a non-numeric strengthen must still be
    # rejected rather than slipping into a declared-numeric field
    base = _base("dpa-clauses")
    overlay = {"extends": "shared-infra-dpa-clauses", "strengthen": {"clauses": {"DPA01": {"sla_hours": "soon"}}}}
    result = ov.apply_overlay(base, overlay)
    assert not result.ok
    assert any(v.kind == "invalid_overlay" for v in result.violations)
