---
name: incident-readiness-check
description: Walk a user through the shared-infrastructure incident-readiness check. Loads the responsibility-matrix and DPA definitions, gathers the org's assignments via dialogue, runs `siir check-responsibility` / `siir check-dpa` in JSON mode, and reports PASS/REVISE/BLOCK with the first gap to fix. Use when the user wants to evaluate whether a shared platform (OEM /共通基盤) is ready for the first 30 minutes of an incident.
---

# incident-readiness-check

Interactively score a shared infrastructure's incident readiness against the
definitions in this repository. This skill is a thin wrapper around the `siir`
CLI: it gathers the responsibility-boundary assignments and DPA clause coverage
via dialogue, runs the CLI in JSON mode, and translates the verdict back into a
readable summary plus the first gap to fix.

## When to use this skill

- The user runs a shared SaaS / OEM platform and wants to know whether the
  incident-initial-response responsibilities are clearly assigned
- The user asks to "do a readiness check" / "責任分界を点検" / "事故初動の備えを評価"
- The user wants to score against an overlay (their own company's stricter rules)

## Workflow

0. Decide the overlay list first, and use the SAME list (same order) in every
   step below. Overlays add items, so discovering questions from the base
   definition while scoring with an overlay would silently skip the added
   items (e.g. RB20-RB24 from `overlays/agentic-attacker/responsibility.yaml`,
   the bundled official overlay). Validate each overlay with
   `bin/siir check-overlay <path>` before use.

1. Read the effective (overlay-applied) definition — not the base file — to
   retrieve the items and roles:
   `bin/siir list-definitions --format json --overlay <path> ...` and take the
   `ids` of the responsibility-matrix entry. Do not hard-code item lists; the
   base alone has 12 items, but overlays extend it.

2. For each item (including overlay-added ones), ask who is Accountable /
   Responsible / Consulted / Informed. Where the org genuinely has not
   decided, record `tbd` (the framework treats an explicit `tbd` as a healthy
   gray zone, not a failure).

3. Write the answers to a temp YAML:

   ```yaml
   target: <platform name>
   matrix:
     RB01: { principal_isp: R, oem_operator: C, ops_bpo: I, sw_vendor: I }
     ...
   ```

4. Run `bin/siir check-responsibility <tmp.yaml> --format json` with the same
   `--overlay <path>` list (same order) chosen in step 0. Capture stdout and
   the exit code.

5. Optionally gather DPA clause coverage and run
   `bin/siir check-dpa <dpa.yaml> --format json`.

6. Translate the JSON: lead with the conclusion (PASS / REVISE / BLOCK), then
   list the items that are `block` (unassigned / no accountable / split A) and
   the items that are `revise` (gray zones to resolve). Recommend fixing the
   `block` items first, then re-running.

## Failure modes to handle

- If `bin/siir` is not on PATH, fall back to `python -m siir.cli ...` with
  `PYTHONPATH=<repo>/src`.
- If the overlay fails `check-overlay`, surface the violation and stop rather
  than scoring with a half-applied overlay.
