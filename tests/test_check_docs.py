from __future__ import annotations

import importlib.util
from pathlib import Path
import re


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_docs.py"
SPEC = importlib.util.spec_from_file_location("check_docs", SCRIPT)
assert SPEC and SPEC.loader
check_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_docs)


def test_commonmark_parser_resolves_reference_and_parenthesized_links(tmp_path):
    document = tmp_path / "doc.md"
    document.write_text(
        "[reference][target]\n\n[inline](folder/file_(v1).md)\n\n"
        "[target]: other.md#section\n",
        encoding="utf-8",
    )
    assert check_docs.markdown_link_targets(document) == [
        "other.md#section",
        "folder/file_(v1).md",
    ]


def test_heading_slugger_handles_unicode_and_duplicates(tmp_path):
    document = tmp_path / "doc.md"
    document.write_text("# 通知 SLA\n\n## 通知 SLA\n", encoding="utf-8")
    assert check_docs.heading_slugs(document) == {"通知-sla", "通知-sla-1"}


def test_missing_anchor_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("[bad](target.md#missing)\n", encoding="utf-8")
    target.write_text("# Existing\n", encoding="utf-8")
    is_local, error = check_docs.check_one_local_link(source, "target.md#missing", {})
    assert is_local
    assert error and "missing anchor" in error


def test_untagged_image_in_guide_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "examples" / "skills").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "1.2.3"\n', encoding="utf-8"
    )
    image = "ghcr.io/suwa-sh/shared-infra-incident-readiness:v1.2.3"
    (tmp_path / "README.md").write_text(image, encoding="utf-8")
    (tmp_path / "README.ja.md").write_text(image, encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text(
        "ghcr.io/suwa-sh/shared-infra-incident-readiness", encoding="utf-8"
    )
    errors, version, _ = check_docs.check_image_references()
    assert version == "v1.2.3"
    assert any("<untagged>" in error for error in errors)


def test_readme_image_version_matches_project_release_version():
    project = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    assert match

    errors, version, _ = check_docs.check_image_references()
    assert errors == []
    assert version == f"v{match.group(1)}"
