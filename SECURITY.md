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

- Open a [GitHub Security Advisory](https://github.com/suwa-sh/shared-infra-incident-readiness/security/advisories/new), or
- Email the maintainer listed in `pyproject.toml`.

Please do not open a public issue for an unfixed vulnerability. We aim to
acknowledge reports within a few business days.

## Supported Versions

The latest release on the default branch is supported. This is a reference
framework; pin a tag if you depend on it in production.
