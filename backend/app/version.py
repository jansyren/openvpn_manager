"""Application version + build metadata.

The version is sourced from the installed package metadata (pyproject.toml's
`version`), so there is a single source of truth. Git commit and build time are
optional and populated from env vars at container build time (see Dockerfile);
they read "unknown" when not set.
"""
import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    VERSION = _pkg_version("openvpn-manager")
except PackageNotFoundError:  # package not installed (unusual in dev)
    VERSION = "0.0.0+unknown"

GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")


def version_info() -> dict[str, str]:
    return {"version": VERSION, "git_commit": GIT_COMMIT, "build_time": BUILD_TIME}
