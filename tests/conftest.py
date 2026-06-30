from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
DEFINITIONS = REPO_ROOT / "definitions"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def examples() -> Path:
    return EXAMPLES


@pytest.fixture
def definitions() -> Path:
    return DEFINITIONS
