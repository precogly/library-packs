# Contributing packs

Thanks for helping grow the library. A pack is read by security teams who make
decisions from it, so a review here cares most about sources and accuracy.

A merged pull request is released at once: every Precogly install sees the
change on its Libraries page within minutes. Review is the only gate.

The project's [security policy](https://github.com/precogly/precogly/blob/main/SECURITY.md)
applies here. Report a security problem in a pack (for example a file that should
not pass the checks) the way the security policy says, not in a public issue.

The app's own [contributing guide](https://github.com/precogly/precogly/blob/main/CONTRIBUTING.md)
also applies: human review of everything you submit, conventional commit PR
titles, and the Contributor License Agreement, which CLA Assistant asks you to
accept on your first pull request.

## What a review looks for

- **Sources.** Each new or changed threat, countermeasure, requirement and
  mapping cites where it comes from. A link in the PR description is fine.
- **Licence.** Say what licence or terms the source has, and that they allow
  this use. Add a row to [NOTICE.md](NOTICE.md) for a new source.
- **Checkable mappings.** A reviewer must be able to check a mapping (threat to
  CWE, countermeasure to ASVS) against the cited source.
- **A version bump.** Raise `version` in `pack.yaml` on every change. The app
  offers an update only when the version changes. CI fails a PR that changes a
  pack without raising it.
- **One pack per PR** where possible. It keeps reviews short.
- **No `demo-` slugs.** That prefix is reserved for the packs bundled with the app.

The [authoring guide](docs/authoring-guide.md) describes every file and field.

## What CI checks

The `Validate` workflow runs on every pull request:

1. **`files`**
   - the tests of the tools in `tools/`,
   - `tools/check_pack_files.py`: only `.yaml`, `.yml`, `.svg` and `.md`
     files, no symlinks, YAML that parses, no script or external links in SVG,
     files up to 2 MB and packs up to 20 MB, packs at
     `packs/<category>/<slug>/`, the slug equal to the folder name, unique slugs,
   - `tools/check_version_bumps.py`: every changed pack has a new version.
2. **`validate`** (required): imports every pack, in dependency order, into a
   pinned version of the Precogly app and runs its validator. Errors and
   warnings both fail.

## Running the checks locally

You need [uv](https://docs.astral.sh/uv/). It installs PyYAML for each script.

```
uv run tools/check_pack_files.py
uv run tools/check_version_bumps.py origin/main
uvx --with 'pyyaml>=6,<7' --from 'pytest>=8,<9' pytest tools/tests
```

To run the app's validator, clone `precogly/precogly` next to this repo and, in
that clone:

```
docker compose up -d db
docker compose run --rm \
  -e LIBRARIES_PATH=/packs-under-test \
  -v "$PWD/../library-packs:/packs-under-test:ro" \
  backend python -m pytest apps/packs/test_shipped_packs_validate.py
```

To see your pack in the app, follow "Trying a pack locally" in the [README](README.md).
