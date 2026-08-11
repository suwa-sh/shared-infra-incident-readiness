from __future__ import annotations

from pathlib import Path
import re


def test_existing_version_image_fails_closed_before_attestation():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert re.search(
        r'INSPECT_ERROR="\$RUNNER_TEMP/image-inspect\.err"\n'
        r'\s+if docker buildx imagetools inspect "\$IMAGE:\$TAG" >/dev/null 2>"\$INSPECT_ERROR"; then\n'
        r'\s+echo "refusing to attest an existing image without verifying its source revision: '
        r'\$IMAGE:\$TAG" >&2\n'
        r'\s+exit 1\n'
        r'\s+fi\n'
        r'\s+if ! \{\n'
        r'\s+grep -Fxq "ERROR: \$IMAGE:\$TAG: not found" "\$INSPECT_ERROR" \|\|\n'
        r'\s+grep -Fxq "ERROR: \$IMAGE:\$TAG: manifest unknown" "\$INSPECT_ERROR" \|\|\n'
        r'\s+grep -Fxq "ERROR: \$IMAGE:\$TAG: name unknown" "\$INSPECT_ERROR"\n'
        r'\s+\}; then\n'
        r'\s+echo "could not confirm that the release image is absent; refusing to publish '
        r'\$IMAGE:\$TAG" >&2\n'
        r'\s+cat "\$INSPECT_ERROR" >&2\n'
        r'\s+exit 1\n'
        r'\s+fi',
        workflow,
    )
    assert "grep -Eiq 'not found|manifest unknown|name unknown'" not in workflow
