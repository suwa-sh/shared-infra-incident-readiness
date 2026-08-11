FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc AS builder

WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements-build.lock pyproject.toml README.md LICENSE /build/
RUN pip install --no-cache-dir --require-hashes -r requirements-build.lock
COPY src /build/src
RUN pip wheel --no-cache-dir --no-build-isolation --no-deps --wheel-dir /wheels .

FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

# The pinned overlay engine version, passed by the release workflow (parsed from
# pyproject). Recorded as an OCI label; the authoritative record is the baked-in
# pip freeze and `siir --version`. Defaults to "unknown" for manual builds.
ARG OVERLAY_ENGINE_VERSION=unknown
# App version, passed by the release workflow (derived from the git tag) so the
# label never drifts from the released version. Defaults to "unknown" for
# manual builds.
ARG APP_VERSION=unknown

LABEL org.opencontainers.image.title="shared-infra-incident-readiness" \
      org.opencontainers.image.description="Diagnose whether a shared infrastructure is ready for the first 30 minutes of an incident." \
      org.opencontainers.image.source="https://github.com/suwa-sh/shared-infra-incident-readiness" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${APP_VERSION}" \
      sh.suwa.overlay-engine.version="${OVERLAY_ENGINE_VERSION}"

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SIIR_ROOT=/app

# Install the fully hashed production dependency set before copying the source,
# so dependency layers remain reproducible and cacheable.
COPY requirements.lock pyproject.toml README.md LICENSE /app/
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY definitions /app/definitions
COPY schemas /app/schemas
COPY overlays /app/overlays
COPY examples /app/examples
COPY --from=builder /wheels /wheels

# Install the locally built application wheel without resolving or downloading
# dependencies. The baked-in freeze records the effective runtime set.
RUN pip install --no-cache-dir --no-deps /wheels/*.whl \
    && pip freeze > /app/requirements.frozen.txt \
    && siir --version \
    && chmod -R a=rX /app

# The CLI only reads bundled definitions and caller-mounted input. A numeric,
# unprivileged identity also works on hosts without a matching passwd entry.
USER 65532:65532

ENTRYPOINT ["siir"]
CMD ["--help"]
