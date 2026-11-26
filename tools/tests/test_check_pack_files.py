from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from check_pack_files import MAX_FILE_BYTES, MAX_PACK_BYTES, check_packs, main
from conftest import write_pack

GOOD_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'


def problems_for(packs_dir: Path) -> list[str]:
    return check_packs(packs_dir).problems


def test_a_clean_tree_passes(packs_dir: Path):
    pack_dir = write_pack(packs_dir, "threat-libraries", "aws")
    (pack_dir / "icons").mkdir()
    (pack_dir / "icons" / "s3.svg").write_text(GOOD_SVG)
    (pack_dir / "README.md").write_text("# AWS\n")
    (pack_dir / "components.yml").write_text("components: []\n")
    assert problems_for(packs_dir) == []
    assert main(["--packs-dir", str(packs_dir)]) == 0


def test_ds_store_is_skipped_outside_git(packs_dir: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (pack_dir / ".DS_Store").write_bytes(b"\x00\x01")
    assert problems_for(packs_dir) == []


@pytest.mark.parametrize("file_name", ["run.py", "notes.txt", "data.json", "Makefile"])
def test_a_disallowed_file_type_fails(packs_dir: Path, file_name: str):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (pack_dir / file_name).write_text("x")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert file_name in problems[0]
    assert "not allowed" in problems[0]
    assert main(["--packs-dir", str(packs_dir)]) == 1


def test_a_symlink_fails(packs_dir: Path, tmp_path: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    outside_file = tmp_path / "outside.yaml"
    outside_file.write_text("a: 1\n")
    (pack_dir / "linked.yaml").symlink_to(outside_file)
    problems = problems_for(packs_dir)
    assert any("linked.yaml" in problem and "symlink" in problem for problem in problems)


def test_a_symlink_tracked_by_git_fails(packs_dir: Path, tmp_path: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (pack_dir / "linked.yaml").symlink_to("pack.yaml")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    problems = problems_for(packs_dir)
    assert any("linked.yaml" in problem and "symlink" in problem for problem in problems)


def test_untracked_files_are_ignored_in_a_git_checkout(packs_dir: Path, tmp_path: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    (pack_dir / "scratch.py").write_text("print('untracked')\n")
    assert problems_for(packs_dir) == []


def test_yaml_that_does_not_parse_fails(packs_dir: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (pack_dir / "threats.yaml").write_text("threats: [unclosed\n")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert "does not parse" in problems[0]


def test_a_file_over_the_size_limit_fails(packs_dir: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (pack_dir / "big.md").write_bytes(b"a" * (MAX_FILE_BYTES + 1))
    problems = problems_for(packs_dir)
    assert any("big.md" in problem and "byte limit" in problem for problem in problems)


def test_a_pack_over_the_size_limit_fails(packs_dir: Path):
    pack_dir = write_pack(packs_dir, "taxonomies", "cwe")
    file_count = MAX_PACK_BYTES // MAX_FILE_BYTES + 1
    for index in range(file_count):
        (pack_dir / f"part-{index}.md").write_bytes(b"a" * MAX_FILE_BYTES)
    problems = problems_for(packs_dir)
    assert problems == [
        f"taxonomies/cwe: pack is {file_count * MAX_FILE_BYTES + (pack_dir / 'pack.yaml').stat().st_size} "
        f"bytes, over the {MAX_PACK_BYTES} byte limit"
    ]


@pytest.mark.parametrize(
    ("svg_text", "expected_fragment"),
    [
        ('<svg><script>alert(1)</script></svg>', "<script>"),
        ('<svg><SCRIPT src="x"/></svg>', "<script>"),
        ('<svg><rect onload="alert(1)"/></svg>', "event attribute"),
        ('<svg><rect\n  onClick = "x"/></svg>', "event attribute"),
        ("<svg><foreignObject><div/></foreignObject></svg>", "foreignObject"),
        ('<svg><a href="https://example.com/"/></svg>', "href"),
        ('<svg><use xlink:href="other.svg#icon"/></svg>', "href"),
        ('<svg><image href="data:image/svg+xml;base64,AAAA"/></svg>', "href"),
        ('<svg><image href="data:text/html,<b>x</b>"/></svg>', "href"),
        ("<svg><image href='javascript:alert(1)'/></svg>", "href"),
    ],
)
def test_unsafe_svg_fails(packs_dir: Path, svg_text: str, expected_fragment: str):
    pack_dir = write_pack(packs_dir, "threat-libraries", "aws")
    (pack_dir / "icon.svg").write_text(svg_text)
    problems = problems_for(packs_dir)
    assert problems, svg_text
    assert any(expected_fragment in problem for problem in problems), problems


@pytest.mark.parametrize(
    "svg_text",
    [
        '<svg><use href="#shape"/></svg>',
        '<svg><use xlink:href="#shape"/></svg>',
        '<svg><image href="data:image/png;base64,iVBORw0KGgo="/></svg>',
        '<svg><image xlink:href="data:image/jpeg;base64,/9j/"/></svg>',
        '<svg><image href="data:image/webp;base64,UklGR"/></svg>',
        '<svg><image href="data:image/gif;base64,R0lGOD"/></svg>',
        "<svg><text>someone=here</text></svg>",
    ],
)
def test_safe_svg_passes(packs_dir: Path, svg_text: str):
    pack_dir = write_pack(packs_dir, "threat-libraries", "aws")
    (pack_dir / "icon.svg").write_text(svg_text)
    assert problems_for(packs_dir) == []


@pytest.mark.parametrize(
    "pack_location",
    [("aws",), ("threat-libraries", "cloud", "aws")],
)
def test_a_pack_at_the_wrong_depth_fails(packs_dir: Path, pack_location: tuple[str, ...]):
    pack_dir = packs_dir.joinpath(*pack_location)
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text("pack:\n  slug: aws\n  version: 1.0.0\n")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert "packs/<category>/<slug>/pack.yaml" in problems[0]


def test_a_slug_that_differs_from_the_folder_fails(packs_dir: Path):
    write_pack(packs_dir, "threat-libraries", "aws", pack_slug="amazon")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert "differs from the folder name" in problems[0]


def test_two_packs_with_one_slug_fail(packs_dir: Path):
    write_pack(packs_dir, "taxonomies", "stride-taxonomy")
    write_pack(packs_dir, "worksheets", "stride-taxonomy")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert "share the slug 'stride-taxonomy'" in problems[0]
    assert "taxonomies/stride-taxonomy" in problems[0]
    assert "worksheets/stride-taxonomy" in problems[0]


def test_a_demo_slug_is_reserved(packs_dir: Path):
    write_pack(packs_dir, "threat-libraries", "demo-aws")
    problems = problems_for(packs_dir)
    assert len(problems) == 1
    assert "reserved" in problems[0]


def test_a_missing_packs_folder_fails(tmp_path: Path):
    assert problems_for(tmp_path / "nowhere") != []
