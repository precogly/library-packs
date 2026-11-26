# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Fail when a pack's files changed but its version did not.

The app offers an update only when an imported pack's version differs from the
one in the catalog, so a change without a version bump never reaches anyone who
already imported the pack.

Compares HEAD with the point where it left the base ref (the same range as
`git diff <base>...HEAD`). A new pack passes. A deleted pack passes. Uses
read-only git commands only.

Usage:
    uv run tools/check_version_bumps.py origin/main
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

PACKS_FOLDER = "packs"


def _git(repository_dir: Path, *git_arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *git_arguments],
        cwd=repository_dir,
        capture_output=True,
        text=True,
    )


def _pack_version_at(repository_dir: Path, revision: str, pack_path: str) -> str | None:
    """The pack's `pack.version` at a revision, or None when the pack is absent."""
    shown = _git(repository_dir, "show", f"{revision}:{pack_path}/pack.yaml")
    if shown.returncode != 0:
        return None
    try:
        pack_document = yaml.safe_load(shown.stdout) or {}
    except yaml.YAMLError:
        return ""
    pack_meta = pack_document.get("pack") or {}
    return str(pack_meta.get("version", "0.0.0"))


def changed_pack_paths(repository_dir: Path, base_revision: str) -> list[str]:
    """Pack folders (packs/<category>/<slug>) with a file changed since the base."""
    diff = _git(
        repository_dir,
        "diff",
        "--name-only",
        f"{base_revision}...HEAD",
        "--",
        PACKS_FOLDER,
    )
    if diff.returncode != 0:
        raise RuntimeError(f"git diff failed: {diff.stderr.strip()}")
    pack_paths = set()
    for changed_file in diff.stdout.splitlines():
        path_parts = changed_file.split("/")
        if len(path_parts) >= 4 and path_parts[0] == PACKS_FOLDER:
            pack_paths.add("/".join(path_parts[:3]))
    return sorted(pack_paths)


def find_missing_bumps(repository_dir: Path, base_revision: str) -> list[str]:
    merge_base = _git(repository_dir, "merge-base", base_revision, "HEAD")
    if merge_base.returncode != 0:
        raise RuntimeError(f"git merge-base failed: {merge_base.stderr.strip()}")
    merge_base_revision = merge_base.stdout.strip()

    problems = []
    for pack_path in changed_pack_paths(repository_dir, base_revision):
        base_version = _pack_version_at(repository_dir, merge_base_revision, pack_path)
        head_version = _pack_version_at(repository_dir, "HEAD", pack_path)
        if base_version is None or head_version is None:
            continue  # a new pack, or a deleted one
        if base_version == head_version:
            problems.append(
                f"{pack_path}: files changed but pack.version is still "
                f"{head_version}. Raise it so installs that imported the pack "
                f"are offered the change."
            )
    return problems


def main(argument_list: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base", help="the base git ref, for example origin/main")
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="the git checkout to inspect (default: the current folder)",
    )
    arguments = parser.parse_args(argument_list)
    try:
        problems = find_missing_bumps(arguments.repository, arguments.base)
    except RuntimeError as git_error:
        print(git_error)
        return 1
    if problems:
        print(f"{len(problems)} pack(s) changed without a version bump:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("Every changed pack has a new version.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
