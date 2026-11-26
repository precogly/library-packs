# Precogly library packs

The full threat-modeling library for [Precogly](https://github.com/precogly/precogly):
taxonomies, compliance standards, threat libraries and worksheets, as YAML.

A **pack** is one folder with a `pack.yaml` and, depending on its type,
components, threats, countermeasures, mappings between them, DFD templates and
icons. Examples: `threat-libraries/aws`, `standards/owasp-asvs`, `taxonomies/cwe`.

## Layout

```
packs/
  taxonomies/<slug>/         STRIDE, CWE, CAPEC, MITRE ATT&CK, ATLAS, OWASP risk lists
  standards/<slug>/          OWASP ASVS, NIST CSF, PCI DSS, SOC 2, IEC 62443 and more
  threat-libraries/<slug>/   AWS, Azure, GCP, AI/ML, OT/ICS, banking and more
  worksheets/<slug>/         Worksheets for facilitated sessions
tools/                       Checks and the release builder
docs/                        Authoring guide and catalog format
```

The folder name is the pack's slug, and every pack sits exactly two levels under
`packs/`.

## How packs reach the app

1. A pull request here changes a pack and raises its `version`.
2. CI checks the files and validates every pack with the app's own validator.
3. A maintainer pushes a release tag, for example `v2026.11.0`. The release
   workflow publishes `catalog.json` and one archive per pack on that release.
4. The app reads `catalog.json` from one pinned release and lists every pack on
   its Libraries page. A pack is downloaded only when someone previews or imports
   it. Importing a pack imports its dependencies first.

An app release moves the pinned release. An operator can also point the app at
another release, or at their own copy, with the `PACK_CATALOG_URL` setting.
The format is in [docs/catalog-format.md](docs/catalog-format.md).

## Demo packs in the app

The app repo bundles three small packs so a fresh install works with no
download: `demo-aws` (a slice of `aws` for the two sample threat models),
`demo-asvs` (a subset of OWASP ASVS) and a copy of `stride-taxonomy`. Those are
edited in the app repo, not here. The `demo-` slug prefix is reserved for them,
and the checks here refuse it.

Item IDs in `demo-aws` match the full `aws` pack. When a pack exists in both
places (STRIDE), the app uses its bundled copy.

## Trying a pack locally

1. Build a catalog from your clone:

   ```
   uv run tools/build_release.py --tag v0.0.0-local --packs-dir packs --output-dir dist
   ```

2. Serve it: `python3 -m http.server 8080 --directory dist`
3. Start the app with `PACK_CATALOG_URL=http://host.docker.internal:8080/catalog.json`
   and open the Libraries page. Your pack is listed and can be imported.

The app's [development setup guide](https://precogly.github.io/precogly/contributing/development-setup/)
has the full steps.

## Writing a pack

- [Authoring guide](docs/authoring-guide.md): every file, field and check.
- [CONTRIBUTING.md](CONTRIBUTING.md): what a review looks for and how to run the checks.

## Licence

The packs and tools are under the [Apache License 2.0](LICENSE). Much of the
content is adapted from third-party sources with their own terms. See
[NOTICE.md](NOTICE.md).
