# Security Policy

## Scope

This repository ships **templates, machine-readable definitions, and a
deterministic CLI** for incident-readiness diagnosis. It contains no secrets,
no network calls, and no runtime services. The CLI reads local YAML/JSON and
prints a verdict.

The sample data under `examples/` (brand names, record counts) is drawn from
**public reporting** of a disclosed incident and is illustrative only.

## Reporting a Vulnerability

If you find a security issue (for example, a way to make the CLI execute
arbitrary code via a crafted definition or overlay file), please report it
privately:

- Open a [GitHub Security Advisory](https://github.com/suwa-sh/shared-infra-incident-readiness/security/advisories/new).

Please do not open a public issue for an unfixed vulnerability. We aim to
acknowledge reports within a few business days.

## Supported Versions

The latest tagged release is supported. This is a reference framework; pin an
immutable tag or digest if you depend on it in production. See
[SUPPORT.md](SUPPORT.md) for the maintenance policy.

## Sensitive Data

The CLI does not send input over the network, but responsibility matrices,
contracts, and incident records may contain confidential data. Minimise and
redact inputs, run with least privilege and read-only mounts, and protect saved
output under your organisation's retention policy. See the Japanese
[operations and data-handling guide](docs/08_operations_and_data_handling.md).
