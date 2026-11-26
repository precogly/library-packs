from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

from build_release import build_release, main
from conftest import write_pack


def make_threat_library(packs_dir: Path) -> Path:
    pack_dir = write_pack(
        packs_dir,
        "threat-libraries",
        "aws",
        version="2.1.0",
        extra_pack_lines=(
            "  description: A small test pack.\n"
            "  author: Tester\n"
            "  tags: [aws, cloud]\n"
            "  depends_on:\n"
            "    - taxonomies/stride-taxonomy\n"
            '    - {pack: cwe, version: "^1.0.0"}\n'
        ),
    )
    (pack_dir / "components.yaml").write_text(
        "components:\n  - id: s3\n  - id: lambda\n  - id: sqs\n"
    )
    (pack_dir / "threats.yaml").write_text("threats:\n  - id: t1\n  - id: t2\n")
    (pack_dir / "countermeasures.yaml").write_text("countermeasures:\n  - id: c1\n")
    (pack_dir / "icons").mkdir()
    (pack_dir / "icons" / "s3.svg").write_text("<svg/>")
    (pack_dir / ".DS_Store").write_bytes(b"\x00")
    return pack_dir


def test_catalog_fields_and_counts(packs_dir: Path, tmp_path: Path):
    make_threat_library(packs_dir)
    taxonomy_dir = write_pack(packs_dir, "taxonomies", "stride-taxonomy")
    (taxonomy_dir / "taxonomy.yaml").write_text(
        "taxonomies:\n  - slug: stride\n    entries: []\n"
    )
    output_dir = tmp_path / "dist"

    catalog = build_release("v2026.11.0", packs_dir, output_dir)

    written_catalog = json.loads((output_dir / "catalog.json").read_text())
    assert written_catalog == catalog
    assert catalog["catalogVersion"] == 1
    assert catalog["release"] == "v2026.11.0"
    assert [entry["path"] for entry in catalog["packs"]] == [
        "taxonomies/stride-taxonomy",
        "threat-libraries/aws",
    ]
    aws_entry = catalog["packs"][1]
    expected_subset = {
        "slug": "aws",
        "name": "Aws",
        "description": "A small test pack.",
        "version": "2.1.0",
        "packType": "full",
        "schemaVersion": 1,
        "author": "Tester",
        "tags": ["aws", "cloud"],
        "componentCount": 3,
        "threatCount": 2,
        "countermeasureCount": 1,
        "taxonomyCount": 0,
        "dependsOn": ["taxonomies/stride-taxonomy", {"pack": "cwe", "version": "^1.0.0"}],
        "archive": "threat-libraries__aws-2.1.0.tar.gz",
    }
    assert {key: aws_entry[key] for key in expected_subset} == expected_subset
    assert catalog["packs"][0]["taxonomyCount"] == 1
    assert catalog["packs"][0]["dependsOn"] == []


def test_defaults_match_the_app(packs_dir: Path, tmp_path: Path):
    pack_dir = packs_dir / "standards" / "bare"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text("pack:\n  slug: bare\n")
    catalog = build_release("v1", packs_dir, tmp_path / "dist")
    entry = catalog["packs"][0]
    assert entry["name"] == "bare"
    assert entry["description"] == ""
    assert entry["version"] == "0.0.0"
    assert entry["packType"] == "technology"
    assert entry["schemaVersion"] == 1
    assert entry["author"] == ""
    assert entry["tags"] == []
    assert entry["archive"] == "standards__bare-0.0.0.tar.gz"


def test_every_hash_and_size_matches_its_archive(packs_dir: Path, tmp_path: Path):
    make_threat_library(packs_dir)
    write_pack(packs_dir, "taxonomies", "cwe")
    output_dir = tmp_path / "dist"
    catalog = build_release("v1", packs_dir, output_dir)
    assert len(catalog["packs"]) == 2
    for entry in catalog["packs"]:
        archive_bytes = (output_dir / entry["archive"]).read_bytes()
        assert entry["archiveSize"] == len(archive_bytes)
        assert entry["sha256"] == hashlib.sha256(archive_bytes).hexdigest()
    written_files = sorted(path.name for path in output_dir.iterdir())
    assert written_files == sorted(
        ["catalog.json"] + [entry["archive"] for entry in catalog["packs"]]
    )


def test_an_archive_unpacks_to_the_slug_folder(packs_dir: Path, tmp_path: Path):
    make_threat_library(packs_dir)
    output_dir = tmp_path / "dist"
    build_release("v1", packs_dir, output_dir)
    with tarfile.open(output_dir / "threat-libraries__aws-2.1.0.tar.gz") as archive:
        members = archive.getmembers()
        member_names = [member.name for member in members]
        assert member_names == sorted(member_names)
        assert all(name.split("/")[0] == "aws" for name in member_names)
        assert ".DS_Store" not in " ".join(member_names)
        assert all(member.isfile() or member.isdir() for member in members)
        assert all(member.uid == 0 and member.uname == "" for member in members)
        unpack_dir = tmp_path / "unpacked"
        archive.extractall(unpack_dir, filter="data")
    assert (unpack_dir / "aws" / "pack.yaml").is_file()
    assert (unpack_dir / "aws" / "icons" / "s3.svg").read_text() == "<svg/>"


def test_main_writes_the_output(packs_dir: Path, tmp_path: Path):
    write_pack(packs_dir, "taxonomies", "cwe")
    output_dir = tmp_path / "dist"
    assert (
        main(
            [
                "--tag",
                "v2026.11.0",
                "--packs-dir",
                str(packs_dir),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    assert (output_dir / "catalog.json").exists()
    assert main(["--tag", "v1", "--packs-dir", str(tmp_path / "missing")]) == 1


def test_counts_for_standards_taxonomies_and_templates(packs_dir: Path, tmp_path: Path):
    standard_dir = write_pack(
        packs_dir,
        "standards",
        "cra",
        extra_pack_lines=(
            "frameworks:\n"
            "- slug: cra-2024\n"
            "  requirements:\n"
            "  - {section_code: A1}\n"
            "  - {section_code: A2}\n"
            "- slug: cra-annex\n"
            "  requirements:\n"
            "  - {section_code: B1}\n"
        ),
    )
    taxonomy_dir = write_pack(packs_dir, "taxonomies", "cwe")
    (taxonomy_dir / "taxonomy.yaml").write_text(
        "taxonomies:\n"
        "  - slug: cwe\n"
        "    entries: [{external_id: CWE-1}, {external_id: CWE-2}, {external_id: CWE-3}]\n"
    )
    library_dir = write_pack(packs_dir, "threat-libraries", "aws")
    (library_dir / "dfd-templates").mkdir()
    (library_dir / "dfd-templates" / "one.yaml").write_text("template: {slug: one}\n")
    (library_dir / "dfd-templates" / "two.yaml").write_text("template: {slug: two}\n")
    assert standard_dir.exists()

    catalog = build_release("v1", packs_dir, tmp_path / "dist")
    counts = {
        entry["slug"]: (
            entry["frameworkCount"],
            entry["requirementCount"],
            entry["taxonomyEntryCount"],
            entry["templateCount"],
        )
        for entry in catalog["packs"]
    }

    assert counts == {
        "cra": (2, 3, 0, 0),
        "cwe": (0, 0, 3, 0),
        "aws": (0, 0, 0, 2),
    }
