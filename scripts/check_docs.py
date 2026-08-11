#!/usr/bin/env python3
"""Validate documentation links, release-image references, and CLI examples."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess  # nosec B404: fixed, argument-list commands only; shell is never used.
import sys
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
IMAGE_NAME = "ghcr.io/suwa-sh/shared-infra-incident-readiness"
SIIR = str(ROOT / "bin" / "siir")
SAMPLE_RESPONSIBILITY = "examples/responsibility/sample-oem-mail.yaml"
AGENTIC_RESPONSIBILITY_OVERLAY = "overlays/agentic-attacker/responsibility.yaml"
IMAGE_REF_RE = re.compile(
    rf"{re.escape(IMAGE_NAME)}(?P<tag>:[A-Za-z0-9._-]+)?"
)
MARKDOWN = MarkdownIt("commonmark")


def documentation_files() -> list[Path]:
    """Return the user-facing Markdown files checked by this script."""
    candidates = [
        ROOT / "README.md",
        ROOT / "README.ja.md",
        ROOT / "CHANGELOG.md",
        ROOT / "COMPATIBILITY.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "MIGRATION.md",
        ROOT / "SECURITY.md",
        ROOT / "SUPPORT.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "examples" / "skills").glob("*/SKILL.md")),
    ]
    return [path for path in candidates if path.is_file()]


def github_slug(text: str) -> str:
    """Approximate GitHub's heading slug for the headings used in this repo."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_~]", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return re.sub(r"\s+", "-", text)


def heading_slugs(path: Path) -> set[str]:
    """Collect GitHub-style anchors, including duplicate-heading suffixes."""
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    fenced = False

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not match:
            continue
        base = github_slug(match.group(1))
        count = counts.get(base, 0)
        counts[base] = count + 1
        slugs.add(base if count == 0 else f"{base}-{count}")

    return slugs


def _child_link_target(child) -> str | None:
    if child.type == "link_open":
        return child.attrGet("href")
    if child.type == "image":
        return child.attrGet("src")
    return None


def markdown_link_targets(path: Path) -> list[str]:
    """Return links resolved by CommonMark, including reference-style links."""
    targets: list[str] = []
    for token in MARKDOWN.parse(path.read_text(encoding="utf-8")):
        for child in token.children or []:
            if target := _child_link_target(child):
                targets.append(target)
    return targets


def parse_link_target(raw: str) -> tuple[str, str]:
    """Split a Markdown link into its path and optional anchor."""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    path, separator, anchor = target.partition("#")
    return unquote(path), unquote(anchor) if separator else ""


def check_one_local_link(
    source: Path,
    raw: str,
    slug_cache: dict[Path, set[str]],
) -> tuple[bool, str | None]:
    """Validate one Markdown link and return whether it was local."""
    path_text, anchor = parse_link_target(raw)
    if re.match(r"^[a-z][a-z0-9+.-]*://", path_text) or path_text.startswith(
        "mailto:"
    ):
        return False, None

    target = source if not path_text else (source.parent / path_text).resolve()
    if not target.exists():
        return True, f"{source.relative_to(ROOT)}: missing link target {path_text}"

    if not anchor or target.suffix.lower() != ".md":
        return True, None

    slugs = slug_cache.setdefault(target, heading_slugs(target))
    if anchor in slugs:
        return True, None
    return (
        True,
        f"{source.relative_to(ROOT)}: missing anchor #{anchor} "
        f"in {target.relative_to(ROOT)}",
    )


def check_local_links(files: list[Path]) -> tuple[list[str], int]:
    """Validate local Markdown paths and heading anchors."""
    errors: list[str] = []
    checked = 0
    slug_cache: dict[Path, set[str]] = {}

    for source in files:
        raw_links = markdown_link_targets(source)
        for raw in raw_links:
            is_local, error = check_one_local_link(source, raw, slug_cache)
            checked += int(is_local)
            if error:
                errors.append(error)

    return errors, checked


def _invalid_image_tags(refs: list[str]) -> list[str]:
    return sorted({tag or "<untagged>" for tag in refs if not tag or tag == ":latest"})


def _check_non_readme_image_refs(document: Path, refs: list[str]) -> list[str]:
    invalid = _invalid_image_tags(refs)
    if not invalid:
        return []
    return [
        f"{document.relative_to(ROOT)}: image references must use an explicit "
        f"version tag: {', '.join(invalid)}"
    ]


def _readme_image_refs(
    readme: Path, text: str, refs: list[str]
) -> tuple[list[str], set[str], set[str]]:
    if not refs:
        return [f"{readme.name}: no {IMAGE_NAME} reference"], set(), set()
    invalid = _invalid_image_tags(refs)
    errors = []
    if invalid:
        errors.append(
            f"{readme.name}: image references must use an explicit version tag: "
            + ", ".join(invalid)
        )
    versions = {
        tag[1:] for tag in refs if tag and re.fullmatch(r":v\d+\.\d+\.\d+", tag)
    }
    paths = set(re.findall(r"/app/[A-Za-z0-9._/-]+", text))
    return errors, versions, paths


def check_image_references() -> tuple[list[str], str, set[str]]:
    """Require one explicit, consistent, already-published README image tag."""
    errors: list[str] = []
    versions_by_file: dict[Path, set[str]] = {}
    image_paths: set[str] = set()

    for document in documentation_files():
        text = document.read_text(encoding="utf-8")
        refs = IMAGE_REF_RE.findall(text)
        if document.name not in {"README.md", "README.ja.md"}:
            errors.extend(_check_non_readme_image_refs(document, refs))
            continue
        readme_errors, versions, paths = _readme_image_refs(document, text, refs)
        errors.extend(readme_errors)
        versions_by_file[document] = versions
        image_paths.update(paths)

    version_sets = list(versions_by_file.values())
    versions = set().union(*version_sets) if version_sets else set()
    if len(versions) != 1 or any(item != versions for item in version_sets):
        rendered = ", ".join(
            f"{path.name}={sorted(values)}" for path, values in versions_by_file.items()
        )
        errors.append(f"README image versions must match: {rendered}")

    version = next(iter(versions), "")
    return errors, version, image_paths


def resolve_command(command: list[str]) -> list[str]:
    """Resolve a trusted command name or repo-relative path to an absolute path."""
    executable = command[0]
    if "/" in executable:
        candidate = Path(executable)
        resolved = candidate if candidate.is_absolute() else ROOT / candidate
        if resolved.is_file():
            return [str(resolved.resolve()), *command[1:]]
    else:
        resolved_name = shutil.which(executable)
        if resolved_name:
            return [resolved_name, *command[1:]]
    raise FileNotFoundError(f"executable not found: {executable}")


def run_process(command: list[str], *, capture_stdout: bool) -> subprocess.CompletedProcess[str]:
    """Run one trusted argument-list command without a shell."""
    resolved = resolve_command(command)
    return subprocess.run(  # nosec B603: resolved executable and shell=False.
        resolved,
        cwd=ROOT,
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def run_command(command: list[str], expected: int = 0) -> str | None:
    """Run one verification command and return an error string on mismatch."""
    try:
        result = run_process(command, capture_stdout=False)
    except FileNotFoundError as error:
        return str(error)
    if result.returncode == expected:
        return None
    detail = result.stderr.strip().splitlines()
    suffix = f": {detail[-1]}" if detail else ""
    return (
        f"expected exit {expected}, got {result.returncode}: "
        f"{' '.join(command)}{suffix}"
    )


def check_cli_examples() -> list[str]:
    """Run the representative workflows documented in the READMEs and guides."""
    commands = [
        ([SIIR, "--help"], 0),
        (
            [
                SIIR,
                "check-responsibility",
                SAMPLE_RESPONSIBILITY,
            ],
            2,
        ),
        ([SIIR, "check-dpa", "examples/dpa/sample-dpa-answers.yaml"], 2),
        (
            [
                SIIR,
                "validate-record",
                "examples/records/sample-incident.json",
                "--level",
                "extended",
            ],
            2,
        ),
        (
            [
                SIIR,
                "render-runbook",
                SAMPLE_RESPONSIBILITY,
                "--scenario",
                "rce-6brand",
            ],
            0,
        ),
        (
            [
                SIIR,
                "tabletop",
                "--scenario",
                "rce-6brand",
                SAMPLE_RESPONSIBILITY,
            ],
            0,
        ),
        (
            [
                SIIR,
                "check-overlay",
                "examples/overlays/sample-company/extra-clauses.yaml",
            ],
            0,
        ),
        (
            [
                SIIR,
                "list-definitions",
                "--format",
                "json",
                "--detail",
                "--overlay",
                AGENTIC_RESPONSIBILITY_OVERLAY,
            ],
            0,
        ),
        (
            [
                SIIR,
                "tabletop",
                "--scenario",
                "agentic-attacker",
                "examples/responsibility/sample-agentic.yaml",
                "--overlay",
                "overlays/agentic-attacker/scenarios.yaml",
                "--overlay",
                AGENTIC_RESPONSIBILITY_OVERLAY,
                "--overlay",
                "overlays/agentic-attacker/incident-raci.yaml",
            ],
            0,
        ),
        (
            [
                SIIR,
                "render-runbook",
                "examples/responsibility/sample-evaluation-containment.yaml",
                "--scenario",
                "evaluation-containment",
                "--overlay",
                "overlays/evaluation-containment/scenarios.yaml",
                "--overlay",
                "overlays/evaluation-containment/responsibility.yaml",
                "--overlay",
                "overlays/evaluation-containment/incident-raci.yaml",
                "--overlay",
                AGENTIC_RESPONSIBILITY_OVERLAY,
            ],
            0,
        ),
    ]
    return [error for command, expected in commands if (error := run_command(command, expected))]


def check_container(version: str, image_paths: set[str]) -> list[str]:
    """Verify that the documented release image and its /app paths exist."""
    if not version:
        return ["cannot check the container without one documented image version"]

    image = f"{IMAGE_NAME}:{version}"
    errors: list[str] = []
    manifest_error = run_command(["docker", "manifest", "inspect", image])
    if manifest_error:
        return [manifest_error]

    try:
        version_result = run_process(
            ["docker", "run", "--rm", "--read-only", image, "--version"],
            capture_stdout=True,
        )
    except FileNotFoundError as error:
        return [str(error)]
    expected_version = version.removeprefix("v")
    if version_result.returncode != 0 or f"siir {expected_version} " not in version_result.stdout:
        errors.append(
            f"{image}: --version did not report siir {expected_version}: "
            f"{version_result.stdout.strip() or version_result.stderr.strip()}"
        )

    for path in sorted(image_paths):
        error = run_command(
            ["docker", "run", "--rm", "--read-only", "--entrypoint", "test", image, "-e", path]
        )
        if error:
            errors.append(f"documented image path is unavailable ({path}): {error}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli",
        action="store_true",
        help="run representative documented CLI workflows",
    )
    parser.add_argument(
        "--container",
        action="store_true",
        help="verify the documented release image and /app paths with Docker",
    )
    parser.add_argument(
        "--container-version",
        metavar="VERSION",
        help="override the README version for a post-release container check",
    )
    args = parser.parse_args()

    files = documentation_files()
    errors, link_count = check_local_links(files)
    image_errors, version, image_paths = check_image_references()
    errors.extend(image_errors)

    if args.cli:
        errors.extend(check_cli_examples())
    if args.container:
        errors.extend(check_container(args.container_version or version, image_paths))
    elif args.container_version:
        errors.append("--container-version requires --container")

    if errors:
        for error in errors:
            print(f"[NG] {error}", file=sys.stderr)
        return 1

    checks = [f"{len(files)} files", f"{link_count} local links", f"image {version}"]
    if args.cli:
        checks.append("documented CLI workflows")
    if args.container:
        checks.append("release container")
    print("[OK] docs-check: " + ", ".join(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
