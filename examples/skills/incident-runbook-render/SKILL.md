---
name: incident-runbook-render
description: Render a shared-infrastructure incident initial-response runbook and Tabletop program from a scenario. Thin wrapper around `siir render-runbook` and `siir tabletop`; takes the org's responsibility-matrix answers + a scenario id and returns the 3-stage runbook (責任境界表 → Runbook → Communication Tree) and a facilitation program. Use when the user wants a runbook or a Tabletop exercise for a specific incident scenario.
---

# incident-runbook-render

Render an initial-response runbook and a Tabletop exercise program from a
machine-readable scenario. This skill is a thin wrapper around the `siir` CLI;
the output is deterministic (same inputs → same Markdown), so it is reviewable.

## When to use this skill

- The user wants an initial-response runbook for a shared-infrastructure
  incident scenario (e.g. "共有 SW の RCE → 6 ブランド同時公表")
- The user wants to run a Tabletop exercise and needs a facilitation program
- The user wants the Communication Tree (誰がいつ何を言うか) laid out

## Workflow

0. Decide the overlay list first, and pass the SAME `--overlay <path>` list
   (same order) to every command below. Overlay-added scenarios (e.g.
   `agentic-attacker` from `overlays/agentic-attacker/scenarios.yaml`) do not
   exist without their overlay — `tabletop` would fail with `unknown scenario`,
   and `list-definitions` without the overlay would not show them. Multi-
   definition commands route each overlay to the definition its `extends`
   targets, so passing all selected overlays everywhere is safe.
   `evaluation-containment` is a three-file bundle: always include its
   scenarios, responsibility, and incident-raci files for a runbook or
   Tabletop. Scenario-only use cannot resolve RB30-RB36 owners or AC20-AC26
   ordering.

1. List available scenarios:
   `bin/siir list-definitions --format json --detail --overlay <path> ...` and
   read the effective `items` from the scenarios, responsibility-matrix, and
   incident-raci definitions. Use their item text, notes, cells, role names,
   and scenario ids; do not hard-code descriptions or counts.

2. Obtain the org's responsibility answers YAML (the same shape used by
   `incident-readiness-check`). If none exists, render against the recommended
   template by passing a minimal answers file with just `target`.

3. Runbook: `bin/siir render-runbook <answers.yaml> --scenario <id>
   --overlay <path> ...`. The output has three stages — responsibility table,
   Day 0-3 runbook, communication tree.

4. Tabletop: `bin/siir tabletop --scenario <id> <answers.yaml>
   --overlay <path> ...`. The output has the scenario overview, timed injects,
   facilitation questions, and the focus items annotated with the owner
   (Accountable, or a sole Responsible) from the org's actual table.

5. Present the Markdown as-is, or summarise the focus items and the first SLA
   the org must hit (from the communication tree deadlines).

## Failure modes to handle

- Unknown scenario id → list valid ids from `list-definitions` and ask.
- If `bin/siir` is not on PATH, fall back to `python -m siir.cli ...` with
  `PYTHONPATH=<repo>/src`.
