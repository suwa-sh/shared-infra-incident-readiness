FROM python:3.12-slim

# The pinned overlay engine version, passed by the release workflow (parsed from
# pyproject). Recorded as an OCI label; the authoritative record is the baked-in
# pip freeze and `siir --version`. Defaults to "unknown" for manual builds.
ARG OVERLAY_ENGINE_VERSION=unknown

LABEL org.opencontainers.image.title="shared-infra-incident-readiness" \
      org.opencontainers.image.description="Diagnose whether a shared infrastructure is ready for the first 30 minutes of an incident." \
      org.opencontainers.image.source="https://github.com/suwa-sh/shared-infra-incident-readiness" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.2.0" \
      sh.suwa.overlay-engine.version="${OVERLAY_ENGINE_VERSION}"

WORKDIR /app
COPY . /app

# Editable install: the CLI resolves the bundled definitions/ and schemas/
# relative to the repo root (Path(__file__).parents[2]), so the source tree must
# stay in place. pip pulls the exact-pinned overlay-scoring-skeleton from PyPI
# (which therefore must be published first). The baked-in freeze is the
# authoritative record of which engine version this image contains.
RUN pip install --no-cache-dir -e . \
    && pip freeze > /app/requirements.frozen.txt \
    && siir --version

ENTRYPOINT ["siir"]
CMD ["--help"]
