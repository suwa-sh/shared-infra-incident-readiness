"""siir — shared-infra-incident-readiness diagnostic toolkit."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("shared-infra-incident-readiness")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0.dev0"
