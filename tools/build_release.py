# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Build a release: one archive per pack plus catalog.json.

The app reads catalog.json to list the packs, then downloads one archive when a
user previews or imports that pack. The format is described in
docs/catalog-format.md.

Usage:
    uv run tools/build_release.py --tag v2026.11.0 --packs-dir packs --output-dir dist

Run tools/check_pack_files.py first. This script trusts the layout it checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

import yaml

CATALOG_VERSION = 1
CATALOG_FILE_NAME = "catalog.json"


def _list_length(file_path: Path, key: str) -> int:
    """Count the items under one key, the way the app counts them.

    Mirrors _count_items_in_file in the app's apps/packs/services.py: a missing
    or unreadable file counts as 0.
    """
    if not file_path.exists():
        return 0
    try:
        document = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return len(document.get(key, []))
    except Exception:
        return 0


def find_pack_dirs(packs_dir: Path) -> list[Path]:
    """Every packs/<category>/<slug> folder that holds a pack.yaml, sorted."""
    return sorted(pack_yaml.parent for pack_yaml in packs_dir.glob("*/*/pack.yaml"))


def _archive_member_filter(member: tarfile.TarInfo) -> tarfile.TarInfo:
    """Drop the builder's user and group, and set plain permissions."""
    member.uid = 0
    member.gid = 0
    member.uname = ""
    member.gname = ""
    member.mode = 0o755 if member.isdir() else 0o644
    return member


def _files_to_archive(pack_dir: Path) -> list[Path]:
    """The pack folder's subfolders and files, sorted, without hidden entries."""
    entries = []
    for entry in sorted(pack_dir.rglob("*")):
        relative_parts = entry.relative_to(pack_dir).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        if entry.is_dir() or entry.is_file():
            entries.append(entry)
    return entries


def write_pack_archive(pack_dir: Path, archive_path: Path) -> None:
    """Write a .tar.gz whose paths start at the pack folder (aws/pack.yaml)."""
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(
            pack_dir,
            arcname=pack_dir.name,
            recursive=False,
            filter=_archive_member_filter,
        )
        for entry in _files_to_archive(pack_dir):
            archive_name = f"{pack_dir.name}/{entry.relative_to(pack_dir).as_posix()}"
            archive.add(
                entry,
                arcname=archive_name,
                recursive=False,
                filter=_archive_member_filter,
            )


def _sha256_of(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as archive_file:
        for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def catalog_entry_for(pack_dir: Path, packs_dir: Path, output_dir: Path) -> dict:
    """Build one pack's archive and return its catalog entry.

    Field defaults match _discover_pack in the app's apps/packs/services.py.
    """
    pack_document = yaml.safe_load((pack_dir / "pack.yaml").read_text(encoding="utf-8"))
    pack_meta = (pack_document or {}).get("pack") or {}
    pack_slug = pack_meta.get("slug", pack_dir.name)
    pack_version = str(pack_meta.get("version", "0.0.0"))
    category = pack_dir.parent.name
    archive_name = f"{category}__{pack_slug}-{pack_version}.tar.gz"
    archive_path = output_dir / archive_name

    write_pack_archive(pack_dir, archive_path)

    return {
        "slug": pack_slug,
        "path": pack_dir.relative_to(packs_dir).as_posix(),
        "name": pack_meta.get("name", pack_slug),
        "description": pack_meta.get("description", ""),
        "version": pack_version,
        "packType": pack_meta.get("pack_type", "technology"),
        "schemaVersion": pack_meta.get("schema_version", 1),
        "author": pack_meta.get("author", ""),
        "tags": pack_meta.get("tags") or [],
        "componentCount": _list_length(pack_dir / "components.yaml", "components"),
        "threatCount": _list_length(pack_dir / "threats.yaml", "threats"),
        "countermeasureCount": _list_length(
            pack_dir / "countermeasures.yaml", "countermeasures"
        ),
        "taxonomyCount": _list_length(pack_dir / "taxonomy.yaml", "taxonomies"),
        "dependsOn": pack_meta.get("depends_on") or [],
        "archive": archive_name,
        "archiveSize": archive_path.stat().st_size,
        "sha256": _sha256_of(archive_path),
    }


def build_release(release_tag: str, packs_dir: Path, output_dir: Path) -> dict:
    """Write every pack archive and catalog.json into output_dir. Returns the catalog."""
    packs_dir = packs_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_entries = [
        catalog_entry_for(pack_dir, packs_dir, output_dir)
        for pack_dir in find_pack_dirs(packs_dir)
    ]
    catalog_entries.sort(key=lambda entry: entry["path"])
    catalog = {
        "catalogVersion": CATALOG_VERSION,
        "release": release_tag,
        "packs": catalog_entries,
    }
    (output_dir / CATALOG_FILE_NAME).write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return catalog


def main(argument_list: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tag", required=True, help="release tag, for example v2026.11.0")
    parser.add_argument("--packs-dir", type=Path, default=Path("packs"))
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    arguments = parser.parse_args(argument_list)
    if not arguments.packs_dir.is_dir():
        print(f"packs folder not found: {arguments.packs_dir}")
        return 1
    catalog = build_release(arguments.tag, arguments.packs_dir, arguments.output_dir)
    print(
        f"Wrote {len(catalog['packs'])} pack archives and {CATALOG_FILE_NAME} "
        f"to {arguments.output_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
