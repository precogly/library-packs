"""The version check runs against a real git repository built in the test's temp folder."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from check_version_bumps import find_missing_bumps, main
from conftest import write_pack


def run_git(repository_dir: Path, *git_arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *git_arguments,
        ],
        cwd=repository_dir,
        check=True,
        capture_output=True,
    )


def commit_everything(repository_dir: Path, message: str) -> None:
    run_git(repository_dir, "add", "-A")
    run_git(repository_dir, "commit", "-q", "--allow-empty", "-m", message)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository with one pack on a base branch and a feature branch checked out."""
    repository_dir = tmp_path / "repository"
    repository_dir.mkdir()
    run_git(repository_dir, "init", "-q", "-b", "base")
    write_pack(repository_dir / "packs", "threat-libraries", "aws", version="1.0.0")
    write_pack(repository_dir / "packs", "taxonomies", "cwe", version="2.0.0")
    commit_everything(repository_dir, "base")
    run_git(repository_dir, "checkout", "-q", "-b", "feature")
    return repository_dir


def test_no_change_passes(repository: Path):
    commit_everything(repository, "nothing")
    assert find_missing_bumps(repository, "base") == []


def test_a_change_without_a_bump_fails(repository: Path):
    (repository / "packs/threat-libraries/aws/threats.yaml").write_text("threats: []\n")
    commit_everything(repository, "change aws")
    problems = find_missing_bumps(repository, "base")
    assert len(problems) == 1
    assert problems[0].startswith("packs/threat-libraries/aws:")
    assert "1.0.0" in problems[0]
    assert main(["base", "--repository", str(repository)]) == 1


def test_a_change_with_a_bump_passes(repository: Path):
    (repository / "packs/threat-libraries/aws/threats.yaml").write_text("threats: []\n")
    write_pack(repository / "packs", "threat-libraries", "aws", version="1.1.0")
    commit_everything(repository, "change aws and bump")
    assert find_missing_bumps(repository, "base") == []
    assert main(["base", "--repository", str(repository)]) == 0


def test_only_the_unbumped_pack_is_reported(repository: Path):
    (repository / "packs/threat-libraries/aws/threats.yaml").write_text("threats: []\n")
    write_pack(repository / "packs", "threat-libraries", "aws", version="1.1.0")
    (repository / "packs/taxonomies/cwe/taxonomy.yaml").write_text("taxonomies: []\n")
    commit_everything(repository, "two packs")
    problems = find_missing_bumps(repository, "base")
    assert len(problems) == 1
    assert problems[0].startswith("packs/taxonomies/cwe:")


def test_a_new_pack_passes(repository: Path):
    write_pack(repository / "packs", "threat-libraries", "gcp")
    commit_everything(repository, "new pack")
    assert find_missing_bumps(repository, "base") == []


def test_a_deleted_pack_passes(repository: Path):
    shutil.rmtree(repository / "packs/taxonomies/cwe")
    commit_everything(repository, "remove cwe")
    assert find_missing_bumps(repository, "base") == []


def test_changes_on_the_base_after_branching_are_not_counted(repository: Path):
    run_git(repository, "checkout", "-q", "base")
    (repository / "packs/taxonomies/cwe/taxonomy.yaml").write_text("taxonomies: []\n")
    commit_everything(repository, "change on base")
    run_git(repository, "checkout", "-q", "feature")
    assert find_missing_bumps(repository, "base") == []


def test_an_unknown_base_fails(repository: Path):
    assert main(["no-such-ref", "--repository", str(repository)]) == 1
