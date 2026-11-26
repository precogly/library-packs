# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Check the files under packs/ before they are validated or released.

This is a safety and layout check, not the pack validator. The validator runs in
the app (see .github/workflows/validate.yml). This check refuses files the app
must never receive: unexpected file types, symlinks, SVG that can run script,
files too large for the app's download limit, and packs in the wrong place.

In a git checkout it checks the files git tracks, so an untracked .DS_Store on a
contributor's machine does not fail it. Outside a git checkout it walks the
folder and skips .DS_Store.

Usage:
    uv run tools/check_pack_files.py [--packs-dir packs]

Exit status 0 when every check passes, 1 with a list of problems otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ALLOWED_SUFFIXES = {".yaml", ".yml", ".svg", ".md"}
MAX_FILE_BYTES = 2 * 1024 * 1024
# The app refuses a pack archive above 20 MB (PACK_DOWNLOAD_MAX_BYTES). Checking
# the unpacked size against the same number keeps every pack that passes here
# under that limit, since a compressed archive is never larger than its files.
MAX_PACK_BYTES = 20 * 1024 * 1024
RESERVED_SLUG_PREFIX = "demo-"
IGNORED_FILE_NAMES = {".DS_Store"}

_TAG_RE = re.compile(r"<[^>]*>", re.DOTALL)
_EVENT_ATTRIBUTE_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_HREF_RE = re.compile(
    r"""\b(?:xlink:)?href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE
)
_ALLOWED_DATA_URI_RE = re.compile(
    r"^data:image/(?:png|jpeg|gif|webp)[;,]", re.IGNORECASE
)


@dataclass
class CheckReport:
    problems: list[str] = field(default_factory=list)

    def add(self, relative_path: str, message: str) -> None:
        self.problems.append(f"{relative_path}: {message}")


def _git_toplevel(directory: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(completed.stdout.strip())


def list_pack_files(packs_dir: Path) -> tuple[list[Path], set[Path]]:
    """Return the files to check and the subset git records as symlinks.

    Paths are absolute. In a git checkout these are the tracked files only.
    """
    packs_dir = packs_dir.resolve()
    git_root = _git_toplevel(packs_dir)
    if git_root is not None:
        completed = subprocess.run(
            ["git", "ls-files", "-s", "-z", "--", str(packs_dir)],
            cwd=git_root,
            capture_output=True,
            check=True,
        )
        tracked_files: list[Path] = []
        git_symlinks: set[Path] = set()
        for record in completed.stdout.decode().split("\0"):
            if not record:
                continue
            metadata, _, relative_name = record.partition("\t")
            file_mode = metadata.split(" ", 1)[0]
            absolute_path = git_root / relative_name
            tracked_files.append(absolute_path)
            if file_mode == "120000":
                git_symlinks.add(absolute_path)
        if tracked_files:
            return sorted(tracked_files), git_symlinks

    walked_files: list[Path] = []
    for candidate in sorted(packs_dir.rglob("*")):
        if candidate.name in IGNORED_FILE_NAMES:
            continue
        if candidate.is_symlink() or candidate.is_file():
            walked_files.append(candidate)
    return walked_files, set()


def _check_svg(svg_text: str) -> list[str]:
    problems = []
    lowered_text = svg_text.lower()
    if "<script" in lowered_text:
        problems.append("SVG contains <script>")
    if "<foreignobject" in lowered_text:
        problems.append("SVG contains <foreignObject>")
    for tag_text in _TAG_RE.findall(svg_text):
        if _EVENT_ATTRIBUTE_RE.search(tag_text):
            problems.append(f"SVG has an event attribute in {tag_text[:80]!r}")
        for href_match in _HREF_RE.finditer(tag_text):
            href_value = next(
                group for group in href_match.groups() if group is not None
            ).strip()
            if href_value.startswith("#"):
                continue
            if _ALLOWED_DATA_URI_RE.match(href_value):
                continue
            problems.append(
                f"SVG href must be a #fragment or a raster image data: URI, "
                f"found {href_value[:60]!r}"
            )
    return problems


def check_packs(packs_dir: Path) -> CheckReport:
    report = CheckReport()
    packs_dir = packs_dir.resolve()
    if not packs_dir.is_dir():
        report.add(str(packs_dir), "packs folder not found")
        return report

    files_to_check, git_symlinks = list_pack_files(packs_dir)
    pack_bytes: dict[Path, int] = defaultdict(int)
    pack_dirs: list[Path] = []

    for file_path in files_to_check:
        relative_path = file_path.relative_to(packs_dir).as_posix()
        relative_parts = file_path.relative_to(packs_dir).parts

        if file_path in git_symlinks or file_path.is_symlink():
            report.add(relative_path, "symlinks are not allowed")
            continue
        folders_inside_packs = [
            packs_dir.joinpath(*relative_parts[:depth])
            for depth in range(1, len(relative_parts))
        ]
        if any(folder.is_symlink() for folder in folders_inside_packs):
            report.add(relative_path, "a parent folder is a symlink")
            continue
        if not file_path.exists():
            # Tracked but deleted in the working tree: nothing to read.
            continue
        if file_path.suffix.lower() not in ALLOWED_SUFFIXES:
            report.add(
                relative_path,
                f"file type {file_path.suffix or '(none)'} is not allowed; "
                f"allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}",
            )
            continue

        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_BYTES:
            report.add(
                relative_path,
                f"file is {file_size} bytes, over the {MAX_FILE_BYTES} byte limit",
            )
        if len(relative_parts) >= 3:
            pack_bytes[packs_dir / relative_parts[0] / relative_parts[1]] += file_size

        if file_path.suffix.lower() in {".yaml", ".yml"}:
            try:
                yaml.safe_load(file_path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, UnicodeDecodeError) as parse_error:
                report.add(relative_path, f"YAML does not parse: {parse_error}")
        elif file_path.suffix.lower() == ".svg":
            try:
                svg_text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                report.add(relative_path, "SVG is not UTF-8 text")
                continue
            for svg_problem in _check_svg(svg_text):
                report.add(relative_path, svg_problem)

        if file_path.name == "pack.yaml":
            if len(relative_parts) != 3:
                report.add(
                    relative_path,
                    "a pack must sit exactly at packs/<category>/<slug>/pack.yaml",
                )
            else:
                pack_dirs.append(file_path.parent)

    for pack_dir, total_bytes in sorted(pack_bytes.items()):
        if total_bytes > MAX_PACK_BYTES:
            report.add(
                pack_dir.relative_to(packs_dir).as_posix(),
                f"pack is {total_bytes} bytes, over the {MAX_PACK_BYTES} byte limit",
            )

    packs_by_slug: dict[str, list[str]] = defaultdict(list)
    for pack_dir in pack_dirs:
        relative_pack_path = pack_dir.relative_to(packs_dir).as_posix()
        try:
            pack_document = yaml.safe_load(
                (pack_dir / "pack.yaml").read_text(encoding="utf-8")
            )
        except (yaml.YAMLError, UnicodeDecodeError):
            continue  # already reported above
        pack_meta = (pack_document or {}).get("pack") or {}
        pack_slug = pack_meta.get("slug")
        if not isinstance(pack_slug, str) or not pack_slug:
            report.add(f"{relative_pack_path}/pack.yaml", "pack.slug is missing")
            continue
        if pack_slug != pack_dir.name:
            report.add(
                f"{relative_pack_path}/pack.yaml",
                f"pack.slug {pack_slug!r} differs from the folder name {pack_dir.name!r}",
            )
        if pack_slug.startswith(RESERVED_SLUG_PREFIX):
            report.add(
                f"{relative_pack_path}/pack.yaml",
                f"slugs starting with {RESERVED_SLUG_PREFIX!r} are reserved for "
                f"packs bundled with the app",
            )
        packs_by_slug[pack_slug].append(relative_pack_path)

    for pack_slug, pack_paths in sorted(packs_by_slug.items()):
        if len(pack_paths) > 1:
            report.add(
                ", ".join(pack_paths), f"these packs share the slug {pack_slug!r}"
            )

    return report


def main(argument_list: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "packs",
        help="folder holding <category>/<slug>/pack.yaml (default: packs/)",
    )
    arguments = parser.parse_args(argument_list)
    report = check_packs(arguments.packs_dir)
    if report.problems:
        print(f"{len(report.problems)} problem(s) found:")
        for problem in report.problems:
            print(f"  {problem}")
        return 1
    print("Pack file checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
