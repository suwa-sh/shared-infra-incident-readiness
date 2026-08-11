---
name: incident-runbook-render
description: Render a shared-infrastructure initial-response runbook and Tabletop program from an organisation's responsibility answers and a scenario. Use the SIIR CLI to return the responsibility table, ordered runbook, Communication Tree, and facilitation program. Use when a user needs a runbook or Tabletop exercise for a specific incident scenario.
---

# incident-runbook-render

Use this skill to render an initial-response runbook and a Tabletop exercise from machine-readable SIIR definitions.
The skill is a thin wrapper around `siir render-runbook` and `siir tabletop` and must not reproduce their rendering logic.

## When to use this skill

- A user wants an initial-response runbook for a shared-infrastructure incident scenario.
- A user needs a facilitation program for a Tabletop exercise.
- A user wants to review the Communication Tree, including who communicates, when it triggers, and what the message may contain.

## Workflow

### 1. Select and validate overlays

Decide the complete ordered overlay list before selecting a scenario.
Pass the same list, in the same order, to every command in this workflow.

Validate every selected overlay first.

```bash
bin/siir check-overlay <path>
```

Multi-definition commands route each file to the definition named by its `extends` value.
An overlay-added scenario does not exist unless its scenario file is included.

Treat `evaluation-containment` as a three-file bundle.
Include its scenarios, responsibility, and incident-raci files so that the CLI can resolve RB30 through RB36 owners and AC20 through AC26 ordering.

### 2. Inspect effective scenarios and definitions

```bash
bin/siir list-definitions \
  --format json \
  --detail \
  --overlay <path> ...
```

Read the effective `items` from the scenarios, responsibility-matrix, and incident-raci entries.
Use their text, notes, cells, role names, and scenario IDs.
Do not hard-code descriptions or counts.

### 3. Obtain responsibility answers

Use an answers YAML with the same shape as `incident-readiness-check`.
If the organisation has no completed matrix, explain that blank cells fall back to the definition's `recommended` values.
Use a minimal file containing only `target` only when the user accepts that fallback.

### 4. Render the runbook

```bash
bin/siir render-runbook \
  <answers.yaml> \
  --scenario <id> \
  --overlay <path> ...
```

The output has three stages: the responsibility table, the ordered initial-response activities, and the Communication Tree.

### 5. Render the Tabletop program

```bash
bin/siir tabletop \
  --scenario <id> \
  <answers.yaml> \
  --overlay <path> ...
```

The output includes the scenario overview, timed injects, facilitation questions, and focus-item owners derived from the organisation's answers.

### 6. Present the result

Return the generated Markdown unchanged when the user wants an operational artifact.
When the user wants a review summary, lead with unresolved owners and the first notification deadline.
Distinguish values supplied by the organisation from `recommended` fallback values.

## Failure modes

- If the scenario ID is unknown, list valid IDs from the effective definitions and ask the user to choose one.
- If `bin/siir` is unavailable, run `python -m siir.cli ...` with `PYTHONPATH=<repo>/src`.
- If a reference cannot be resolved, confirm that all files in the selected overlay bundle were passed in the same order.
- If `check-overlay` fails, report the violation and stop before rendering.
