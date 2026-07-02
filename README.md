# shared-infra-incident-readiness

![OGP](docs/assets/ogp.png)

[![CI](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml/badge.svg)](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇯🇵 日本語版は [README.ja.md](README.ja.md)

A diagnostic tool and extensible framework for **the first 30 minutes of a
shared-infrastructure incident**: who is accountable, which DPA clauses are
missing, whether the notification timeline meets its SLA, and how to run the
Tabletop exercise. Distilled from the **published analysis** of a shared mail
platform incident (an OEM platform shared by six ISPs).

Key features:

1. **Diagnoses your incident readiness** — it mechanically checks responsibility
   boundaries, contract (DPA) clauses and notification SLAs, and returns a
   deterministic verdict.
2. **A machine-readable single source of truth** — the responsibility table,
   RACI, DPA clauses, notification obligations and scenarios are kept as
   definitions that AI agents and CI can consume directly.
3. **Extensible without forking** — each company adds its own roles, items,
   clauses, obligations and scenarios through an overlay.

> **Glossary**: **DPA** (Data Processing Agreement) is the contract between the
> entrusting party (controller) and the processor governing how personal data is
> handled. **RACI** organises responsibility into four roles — Responsible /
> Accountable / Consulted / Informed. **SLA** here means the deadline by which a
> notification must be sent.

> **A note on language**: Documents under `docs/` are written in Japanese (the
> author's working language). This English README is the entry point;
> [README.ja.md](README.ja.md) is the canonical text.

## Quick start (3 minutes)

No setup — pull the published image and run it. The bundled samples work out
of the box:

```bash
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 --version

# 1. Score a filled responsibility-boundary matrix
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  check-responsibility examples/responsibility/sample-oem-mail.yaml

# 2. Check DPA clause coverage
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  check-dpa examples/dpa/sample-dpa-answers.yaml

# 3. Validate an incident record + its notification SLA timeline
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  validate-record examples/records/sample-incident.json --level extended

# 4. Render a 3-stage runbook (responsibility table -> runbook -> comms tree)
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  render-runbook examples/responsibility/sample-oem-mail.yaml --scenario rce-6brand

# 5. Render a Tabletop exercise program
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  tabletop --scenario rce-6brand examples/responsibility/sample-oem-mail.yaml

# 6. Validate an overlay (add / strengthen only) and inspect definitions
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  check-overlay examples/overlays/sample-company/extra-clauses.yaml
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 list-definitions
```

`--version` prints the app version and the bundled overlay engine version, e.g.
`siir 0.2.0 (overlay-scoring-skeleton 0.1.0)`.

Every command returns a deterministic exit code so you can gate CI on it:
**0** ok · **1** partial (yellow: warnings, deferred items, not-yet-sent
notifications) · **2** block (gaps, missing clauses, SLA breach, rejected
overlay) · **3** input error (file missing / parse error).

## Usage workflow

The commands run against *your* data. Mount the directory that holds your files
into the container. A shell function keeps the rest of this guide readable:

```bash
siir() { docker run --rm -v "$PWD:/data" -w /data \
  ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 "$@"; }
```

Grab a sample from [`examples/`](examples/) as a template, edit it with your own
values, then run the commands in this order — from peacetime preparation to
incident-time validation.

1. **Prepare** — start your own input files from a sample
   (`my-responsibility.yaml`, `my-dpa.yaml`).
2. **Check responsibilities (peacetime)** — fill the `matrix` with your own
   R/A/C/I (write `tbd` for a box you have not decided yet), then
   `siir check-responsibility my-responsibility.yaml`. Fix `BLOCK` rows
   first, then the `REVISE` gray zones.
3. **Check the contract (peacetime)** — mark each clause `present` / `partial` /
   `missing` in a copy of `examples/dpa/sample-dpa-answers.yaml`, then
   `siir check-dpa my-dpa.yaml`.
4. **Prepare runbooks & drills** — generate the deterministic 3-stage runbook and
   the Tabletop program:
   `siir render-runbook my-responsibility.yaml --scenario rce-6brand` and
   `siir tabletop --scenario rce-6brand my-responsibility.yaml`
   (list scenario ids with `siir list-definitions`).
5. **Validate at incident time** — build a real incident record from
   `examples/records/sample-incident.json` and check the notification timeline:
   `siir validate-record my-incident.json --level extended`.
6. **Extend (optional)** — add your own roles / clauses / scenarios via an
   overlay, validated by `siir check-overlay <path>` and applied with
   `--overlay <path>`.

Sample output (`check-responsibility`) — `[OK]` ok / `[..]` revise / `[NG]` block
per row, then an overall verdict:

```text
Target: 共用メール基盤 (6 ISP OEM)
Responsibility readiness: 83%

[OK] RB01 利用者向け窓口・本人通知: OK (ok)
[..] RB04 プレスリリース (共同 / 個別の決定): REVISE (accountability_deferred)
    gray (tbd): oem_operator
[NG] RB12 平時 / 事故時の合同演習主催: BLOCK (unassigned)

Conclusion: BLOCK
```

See [`README.ja.md`](README.ja.md#使い方想定ワークフロー) for sample output of every
command in the workflow.

## Who this is for

| If you are... | Start with... |
|---|---|
| A **PMO / security lead** at an OEM / shared-platform operator | [`docs/01_responsibility_boundary.md`](docs/01_responsibility_boundary.md) — fill your matrix, run `check-responsibility` |
| A **legal / procurement** owner of an outsourcing contract | [`docs/03_dpa_clauses.md`](docs/03_dpa_clauses.md) — check the 10 mandatory DPA clauses |
| An **engineer / SRE** wiring an incident record pipeline | [`schemas/incident-record.schema.json`](schemas/incident-record.schema.json) + [`docs/02_incident_raci_and_sla.md`](docs/02_incident_raci_and_sla.md) |
| A **consultant / proposal author** | All `docs/` + the overlay model — clone, overlay in private, present client-specific scoring |

## What's in this repo

```
shared-infra-incident-readiness/
├── definitions/                 # Machine-readable canonical framework (YAML)
│   ├── responsibility-matrix.yaml      # 12 items x 4 roles (R/A/C/I)
│   ├── incident-raci.yaml              # 15 activities x 5 roles (refs obligations/clauses)
│   ├── dpa-clauses.yaml                # 10 DPA clauses (contractual SLA source of truth)
│   ├── notification-obligations.yaml   # statutory notification clocks
│   └── scenarios.yaml                  # Tabletop scenarios
├── schemas/incident-record.schema.json # incident record + notification timeline
├── bin/siir + src/siir/                # the CLI
├── examples/                           # sample inputs, overlays, worked example, agent skills
├── docs/                               # design docs (C4, concept model, scoring)
└── tests/                              # overlay / scoring / SLA / runbook boundary conditions
```

## The overlay model

Overlays let a company extend the framework without forking it. Only two
operations are allowed, declared per definition in `extension_points`:

- **`add`** — append a new role / item / clause / obligation / scenario (with a
  fresh `id`). Overwriting or deleting existing entries is rejected.
- **`strengthen`** — move a declared numeric field in the stricter direction
  only (e.g. shorten an SLA from 24h to 12h). Weakening is rejected.

`siir check-overlay <path>` (using the `siir` shell function from
[Usage workflow](#usage-workflow)) validates an overlay before you apply it.

## Development

```bash
pytest tests/                  # boundary conditions, exit codes
bin/siir --help                # CLI smoke
npx md-mermaid-lint docs/*.md  # diagram syntax
```

## License

MIT — see [LICENSE](LICENSE).
