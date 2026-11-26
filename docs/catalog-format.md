# Catalog format

Each release of this repo publishes a `catalog.json` and one archive per pack.
The Precogly app reads `catalog.json` to list the packs on its Libraries page.
It downloads an archive only when someone previews, validates or imports that pack.

`tools/build_release.py` writes both. The release workflow runs it on every tag.

## Files in a release

| File | What it is |
| --- | --- |
| `catalog.json` | The list of packs, described below. |
| `<category>__<slug>-<version>.tar.gz` | One pack. Example: `threat-libraries__aws-4.0.0.tar.gz`. |

The app fetches each archive from the same folder as `catalog.json`. It replaces
the file name in the catalog address with the `archive` value. So a copy of a
release works anywhere, as long as all its files sit in one folder.

## `catalog.json`

```json
{
  "catalogVersion": 1,
  "release": "v2026.11.0",
  "packs": [
    {
      "slug": "azure",
      "path": "threat-libraries/azure",
      "name": "Azure Technologies",
      "description": "Microsoft Azure cloud components for threat modeling diagrams",
      "version": "2.0.0",
      "packType": "technology",
      "schemaVersion": 1,
      "author": "Precogly",
      "tags": ["azure"],
      "componentCount": 45,
      "threatCount": 0,
      "countermeasureCount": 0,
      "taxonomyCount": 0,
      "dependsOn": [],
      "archive": "threat-libraries__azure-2.0.0.tar.gz",
      "archiveSize": 23456,
      "sha256": "64 lowercase hex characters"
    }
  ]
}
```

### Top-level fields

| Field | Meaning |
| --- | --- |
| `catalogVersion` | The format version. It is `1`. It goes up on any breaking change to this file or to the archives. The app refuses a catalog with a version it does not know. |
| `release` | The release tag the catalog was built for. |
| `packs` | One entry per pack, sorted by `path`. |

### Pack fields

| Field | From | Default when `pack.yaml` leaves it out |
| --- | --- | --- |
| `slug` | `pack.slug` | the folder name |
| `path` | `<category>/<slug>`, the folder under `packs/` | |
| `name` | `pack.name` | the slug |
| `description` | `pack.description` | empty |
| `version` | `pack.version` | `0.0.0` |
| `packType` | `pack.pack_type` | `technology` |
| `schemaVersion` | `pack.schema_version` | `1` |
| `author` | `pack.author` | empty |
| `tags` | `pack.tags` | empty list |
| `componentCount` | length of `components` in `components.yaml` | `0` |
| `threatCount` | length of `threats` in `threats.yaml` | `0` |
| `countermeasureCount` | length of `countermeasures` in `countermeasures.yaml` | `0` |
| `taxonomyCount` | length of `taxonomies` in `taxonomy.yaml` | `0` |
| `dependsOn` | `pack.depends_on`, unchanged | empty list |
| `archive` | the archive's file name | |
| `archiveSize` | the archive's size in bytes | |
| `sha256` | the archive's SHA-256, lowercase hex | |

The defaults and counts are the same ones the app uses when it reads a pack
from disk, so a pack looks the same in the list whichever way it arrives.

`dependsOn` entries are written as they appear in `pack.yaml`, for example
`taxonomies/stride-taxonomy`. The app uses only the slug, the part after the
last `/`.

There is no timestamp in the file.

## Archives

- A gzip-compressed tar file.
- Every path starts with the pack's slug: `aws/pack.yaml`, `aws/icons/s3.svg`.
- Only folders and regular files. No links.
- Only `.yaml`, `.yml`, `.svg` and `.md` files. Hidden files such as `.DS_Store` are left out.

The app checks each archive before it uses it: the SHA-256 and size must match
the catalog, every path must start with the slug, and the archive may not be
larger than 20 MB. `tools/check_pack_files.py` holds every pack in this repo to
the same 20 MB limit, so a pack that passes here is never refused there.

## Hosting a catalog yourself

For offline sites, or to try a pack before it is released:

1. Build a release: `uv run tools/build_release.py --tag v2026.11.0-local --packs-dir packs --output-dir dist`,
   or download `catalog.json` and every archive from a published release.
2. Serve the folder over HTTP, for example `python3 -m http.server 8080 --directory dist`.
3. Set `PACK_CATALOG_URL` in the app to the address of `catalog.json`.
