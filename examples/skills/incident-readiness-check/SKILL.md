---
name: incident-readiness-check
description: Walk a user through a shared-infrastructure incident-readiness check. Gather responsibility assignments and DPA coverage, run the SIIR CLI in JSON mode, and report PASS, REVISE, or BLOCK with the first gap to fix. Use when a shared SaaS or OEM platform needs to assess its readiness for the first 30 minutes of an incident.
---

# incident-readiness-check

Use this skill to collect an organisation's responsibility assignments and DPA coverage, then score them with the SIIR CLI.
The skill is a thin wrapper around the CLI and must not implement its own scoring rules.

## When to use this skill

- A shared SaaS or OEM operator wants to check whether initial-response responsibilities have an owner.
- A user asks for a readiness check, a responsibility-boundary review, or an assessment of incident preparation.
- A user wants to apply an official or organisation-specific overlay.

## Workflow

### 1. Select and validate overlays

Decide the ordered overlay list before asking questions.
Otherwise, questions discovered from the base definition can omit overlay-added items such as RB20 through RB24 or RB30 through RB36.

Validate every selected file before applying it.

```bash
bin/siir check-overlay <path>
```

Use the overlay list according to the command type.

| Command type | Overlay argument |
|---|---|
| Multi-definition commands: `list-definitions`, `render-runbook`, `tabletop` | Pass the complete ordered list. The CLI routes each file by its `extends` value. |
| Single-definition commands: `check-responsibility`, `check-dpa`, `validate-record` | Pass only the ordered subset whose `extends` value matches the command's definition. |

Passing an unrelated overlay to a single-definition command is an input error with exit code 3.
For a multi-definition `evaluation-containment` workflow, select its scenarios, responsibility, and incident-raci files as one bundle.

### 2. Read the effective definitions

Read the overlay-applied definition instead of reading only the base YAML.

```bash
bin/siir list-definitions \
  --format json \
  --detail \
  --overlay <path> ...
```

Use `items` and `role_items` from the responsibility-matrix entry.
Use each item's effective `text`, `note`, `recommended`, and role names when asking questions.
Do not hard-code item text, role lists, or item counts.

### 3. Collect responsibility assignments

For every effective item, ask which roles are Accountable, Responsible, Consulted, and Informed.
Record a genuinely undecided assignment as `tbd`.
The CLI reports `tbd` as `REVISE`, which preserves the uncertainty without treating it as an unassigned `BLOCK`.

Write the answers to a temporary YAML file.

```yaml
target: <platform name>
matrix:
  RB01:
    principal_isp: R
    oem_operator: C
    ops_bpo: I
    sw_vendor: I
```

### 4. Run the responsibility check

Pass only the responsibility-matrix subset of the selected overlay list.
Preserve its relative order.

```bash
bin/siir check-responsibility \
  <answers.yaml> \
  --format json \
  --overlay <responsibility-overlay> ...
```

Capture both stdout and the exit code.

### 5. Check DPA coverage when requested

Collect `present`, `partial`, or `missing` for each effective DPA clause.
Run `check-dpa` with only the dpa-clauses subset of the selected overlay list.

```bash
bin/siir check-dpa \
  <dpa-answers.yaml> \
  --format json \
  --overlay <dpa-overlay> ...
```

### 6. Report the result

Lead with `PASS`, `REVISE`, or `BLOCK`.
List `block` items first, including unassigned ownership, missing Accountable ownership, and split Accountable ownership.
Then list `revise` items, including explicit gray zones.
Recommend the first block item to resolve, then rerun the check.

Delete temporary files after reporting unless the user asks to retain them.

## Failure modes

- If `bin/siir` is unavailable, run `python -m siir.cli ...` with `PYTHONPATH=<repo>/src`.
- If `check-overlay` fails, report the violation and stop before scoring.
- If an overlay targets the wrong definition, correct the command-specific subset instead of suppressing the input error.
