"""Shared helpers for the tool tests. No network, no Django."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def write_pack(
    packs_dir: Path,
    category: str,
    slug: str,
    *,
    version: str = "1.0.0",
    pack_slug: str | None = None,
    extra_pack_lines: str = "",
) -> Path:
    """Write a minimal pack at packs_dir/<category>/<slug> and return its folder."""
    pack_dir = packs_dir / category / slug
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        dedent(
            f"""\
            pack:
              schema_version: 1
              slug: {pack_slug or slug}
              name: {slug.title()}
              version: {version}
              pack_type: full
            """
        )
        + extra_pack_lines,
        encoding="utf-8",
    )
    return pack_dir


@pytest.fixture
def packs_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "packs"
    folder.mkdir()
    return folder
