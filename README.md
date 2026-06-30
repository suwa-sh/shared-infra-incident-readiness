# shared-infra-incident-readiness

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇯🇵 日本語版は [README.ja.md](README.ja.md)

A diagnostic tool and extensible framework for **the first 30 minutes of a
shared-infrastructure incident**: who is accountable, which DPA clauses are
missing, whether the notification timeline meets its SLA, and how to run the
Tabletop exercise. Distilled from the **published analysis** of a shared mail
platform incident (an OEM platform shared by six ISPs); the framework is
extracted from public reporting, not from any internal source.

You get three things from a clone:

1. **A CLI diagnostic** — `bin/siir check-responsibility` / `check-dpa` /
   `validate-record` / `render-runbook` / `tabletop` — deterministic, runs in
   seconds, exit-code gated.
2. **Machine-readable definitions** (`definitions/*.yaml`, `schemas/*.json`)
   that AI agents can load as context and CI can call directly.
3. **Overlay extension points** so each company can add its own roles, items,
   clauses, obligations and scenarios **without forking the framework**.

> **A note on language**: Documents under `docs/` are written in Japanese (the
> author's working language). This English README is the entry point;
> [README.ja.md](README.ja.md) is the canonical text.

## Quick start (3 minutes)

```bash
git clone https://github.com/suwa-sh/shared-infra-incident-readiness.git
cd shared-infra-incident-readiness
pip install -r requirements.txt

# 1. Score a filled responsibility-boundary matrix
bin/siir check-responsibility examples/responsibility/sample-oem-mail.yaml

# 2. Check DPA clause coverage
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml

# 3. Validate an incident record + its notification SLA timeline
bin/siir validate-record examples/records/sample-incident.json --level extended

# 4. Render a 3-stage runbook (responsibility table -> runbook -> comms tree)
bin/siir render-runbook examples/responsibility/sample-oem-mail.yaml --scenario rce-6brand

# 5. Render a Tabletop exercise program
bin/siir tabletop --scenario rce-6brand examples/responsibility/sample-oem-mail.yaml

# 6. Validate an overlay (add / strengthen only) and inspect definitions
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml
bin/siir list-definitions
```

Every command returns a deterministic exit code so you can gate CI on it:
**0** ok · **1** partial (yellow: warnings, deferred items, not-yet-sent
notifications) · **2** block (gaps, missing clauses, SLA breach, rejected
overlay) · **3** input error (file missing / parse error).

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

`bin/siir check-overlay <path>` validates an overlay before you apply it.

## Development

```bash
pip install -r requirements.txt pytest
pytest tests/                  # boundary conditions, exit codes
bin/siir --help                # CLI smoke
npx md-mermaid-lint docs/*.md  # diagram syntax
```

## License

MIT — see [LICENSE](LICENSE).
