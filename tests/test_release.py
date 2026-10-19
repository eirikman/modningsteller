"""Release consistency checks for Modningsteller."""

from __future__ import annotations

import json
import re
from pathlib import Path

from custom_components.modningsteller.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / DOMAIN / "manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def _manifest_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def test_manifest_version_is_semver() -> None:
    """The manifest version must be a plain X.Y.Z version."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", _manifest_version())


def test_manifest_version_has_changelog_entry() -> None:
    """Every released manifest version must be described in CHANGELOG.md."""
    version = _manifest_version()
    changelog = CHANGELOG.read_text(encoding="utf-8")

    assert f"## [v{version}]" in changelog, (
        f"CHANGELOG.md has no '## [v{version}]' section for manifest version {version}"
    )
