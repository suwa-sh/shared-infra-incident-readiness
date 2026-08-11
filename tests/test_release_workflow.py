from __future__ import annotations

from pathlib import Path
import re


def test_existing_version_image_fails_closed_before_attestation():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert re.search(
        r'if docker buildx imagetools inspect "\$IMAGE:\$TAG" >/dev/null 2>&1; then\n'
        r'\s+echo "refusing to attest an existing image without verifying its source revision: '
        r'\$IMAGE:\$TAG" >&2\n'
        r'\s+exit 1\n'
        r'\s+else',
        workflow,
    )
