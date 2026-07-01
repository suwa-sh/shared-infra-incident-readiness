"""Command-line entry point for ``siir`` (shared-infra-incident-readiness).

Subcommands:
    check-responsibility   score a filled responsibility-boundary matrix
    check-dpa              check DPA clause coverage
    validate-record        validate an incident record + notification SLA
    render-runbook         render a 3-stage initial-response runbook (L3)
    tabletop               render a Tabletop exercise program (L3)
    check-overlay          validate an overlay's add/strengthen rules
    list-definitions       inspect loaded definitions (+ overlays)

Exit codes (consistent across commands, locked by tests):
    0  ok (green)
    1  partial (yellow: warnings, deferred items, not-yet-sent notifications)
    2  block (red: gaps, missing clauses, SLA breach, rejected overlay)
    3  input error (file missing / parse error / overlay structure error)
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import overlay_scoring
import yaml

from . import (
    check_dpa as _dpa,
    check_responsibility as _resp,
    definitions as _defn,
    list_definitions as _list,
    render_runbook as _runbook,
    tabletop as _tabletop,
    validate_record as _record,
)


def _version_string() -> str:
    """`siir --version` reports the app version and the overlay engine version.

    The engine version is the primary way to see which overlay-scoring-skeleton
    release this build depends on (requirement: engine version visibility).
    """
    try:
        app = _pkg_version("shared-infra-incident-readiness")
    except PackageNotFoundError:  # running from a source checkout
        app = "0.0.0.dev0"
    return f"siir {app} (overlay-scoring-skeleton {overlay_scoring.__version__})"


def _add_common(parser: argparse.ArgumentParser, *, overlay: bool = True) -> None:
    if overlay:
        parser.add_argument(
            "--overlay",
            action="append",
            default=[],
            metavar="PATH",
            help="Overlay file to apply (repeatable; applied in order)",
        )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format (default: text)"
    )


def _emit(text: str) -> None:
    print(text)


def _cmd_check_responsibility(args) -> int:
    try:
        result = _resp.check(args.answers, overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_resp.render_json(result) if args.format == "json" else _resp.render_text(result))
    return _resp.exit_code_for(result)


def _cmd_check_dpa(args) -> int:
    try:
        result = _dpa.check(args.answers, overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_dpa.render_json(result) if args.format == "json" else _dpa.render_text(result))
    return _dpa.exit_code_for(result)


def _cmd_validate_record(args) -> int:
    try:
        result = _record.validate(args.record, level=args.level, overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_record.render_json(result) if args.format == "json" else _record.render_text(result))
    return _record.exit_code_for(result)


def _cmd_render_runbook(args) -> int:
    try:
        model = _runbook.build(args.answers, args.scenario, overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    except KeyError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_runbook.render_json(model) if args.format == "json" else _runbook.render_text(model))
    return 0


def _cmd_tabletop(args) -> int:
    try:
        model = _tabletop.build(args.scenario, answers_path=args.answers, overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    except KeyError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_tabletop.render_json(model) if args.format == "json" else _tabletop.render_text(model))
    return 0


def _cmd_check_overlay(args) -> int:
    result = _list.check_overlay(args.overlay_path)
    _emit(_list.render_overlay_json(result) if args.format == "json" else _list.render_overlay_text(result))
    return 0 if result.ok else 2


def _cmd_list_definitions(args) -> int:
    try:
        summaries = _list.summarize(overlay_paths=args.overlay)
    except _defn.OverlayError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 3
    _emit(_list.render_json(summaries) if args.format == "json" else _list.render_text(summaries))
    return 0


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors exit 3 (input error), not argparse's
    default 2 — exit 2 is reserved for a 'block' verdict in our contract."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(3)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="siir",
        description=(
            "shared-infra-incident-readiness CLI. Diagnose whether a shared "
            "infrastructure is ready for the first 30 minutes of an incident: "
            "responsibility boundaries, DPA clauses, notification SLA, and "
            "Tabletop exercises."
        ),
    )
    parser.add_argument("--version", action="version", version=_version_string())
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-responsibility", help="Score a filled responsibility-boundary matrix")
    p.add_argument("answers", help="Path to the responsibility answers YAML")
    _add_common(p)
    p.set_defaults(func=_cmd_check_responsibility)

    p = sub.add_parser("check-dpa", help="Check DPA clause coverage")
    p.add_argument("answers", help="Path to the DPA answers YAML")
    _add_common(p)
    p.set_defaults(func=_cmd_check_dpa)

    p = sub.add_parser("validate-record", help="Validate an incident record + notification SLA")
    p.add_argument("record", help="Path to the incident record JSON")
    p.add_argument("--level", choices=["minimum", "extended"], default="minimum")
    _add_common(p)
    p.set_defaults(func=_cmd_validate_record)

    p = sub.add_parser("render-runbook", help="Render a 3-stage initial-response runbook")
    p.add_argument("answers", help="Path to the responsibility answers YAML")
    p.add_argument("--scenario", required=True, help="Scenario id (see scenarios.yaml)")
    _add_common(p)
    p.set_defaults(func=_cmd_render_runbook)

    p = sub.add_parser("tabletop", help="Render a Tabletop exercise program")
    p.add_argument("--scenario", required=True, help="Scenario id (see scenarios.yaml)")
    p.add_argument("answers", nargs="?", default=None, help="Optional responsibility answers YAML")
    _add_common(p)
    p.set_defaults(func=_cmd_tabletop)

    p = sub.add_parser("check-overlay", help="Validate an overlay's add/strengthen rules")
    p.add_argument("overlay_path", help="Path to the overlay YAML")
    _add_common(p, overlay=False)
    p.set_defaults(func=_cmd_check_overlay)

    p = sub.add_parser("list-definitions", help="Inspect loaded definitions (+ overlays)")
    _add_common(p)
    p.set_defaults(func=_cmd_list_definitions)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        sys.stderr.write(f"[ERROR] file not found: {e}\n")
        return 3
    except yaml.YAMLError as e:
        sys.stderr.write(f"[ERROR] invalid YAML: {e}\n")
        return 3
    except ValueError as e:  # includes json.JSONDecodeError (a ValueError subclass)
        sys.stderr.write(f"[ERROR] invalid input: {e}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
