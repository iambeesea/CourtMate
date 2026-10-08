# Philippine location data — source and limits

These files seed the `geo_regions`, `geo_provinces`, `geo_cities` and `geo_barangays` tables.

| File | Rows | Columns |
| --- | --- | --- |
| `regions.csv` | 17 | `code`, `name`, `region_name`, `island_group` |
| `provinces.csv` | 81 | `code`, `name`, `region_code` |
| `cities.csv` | 1,634 | `code`, `name`, `region_code`, `province_code`, `is_city` |
| `barangays.csv.gz` | 42,046 | `code`, `name`, `city_code` |

## Source

The Philippine Standard Geographic Code (PSGC) is maintained by the Philippine Statistics Authority (PSA). The files here were built on 2026-10-08 from the JSON rendering of the PSGC served by the open PSGC API at <https://psgc.gitlab.io/api/>, using `api/scripts/build_psgc.py`. Checksums are in `manifest.json`.

PSA's own publication page (<https://psa.gov.ph/classification/psgc>) could not be fetched programmatically because it is protected by a browser challenge.

## Known gaps in this snapshot

The upstream snapshot is older than PSA's current quarterly publication. It lists 17 regions and 81 provinces, so it does **not** yet reflect:

- the division of Maguindanao into Maguindanao del Norte and Maguindanao del Sur (2022);
- the Negros Island Region (2024);
- any barangay created, merged or renamed since the snapshot.

Codes are the 9-digit PSGC codes. PSA has since moved to 10-digit codes; the upstream JSON carries both, and only the 9-digit code is kept here.

## Refreshing

```bash
cd api
python scripts/build_psgc.py --download /tmp/psgc_raw
```

To move to PSA's current publication, download the quarterly PSGC workbook from the PSA page in a browser and extend `build_psgc.py` with a reader for it. The database tables do not need to change.

Coordinates are not part of the PSGC. Facility and meet-up coordinates are supplied by whoever registers them.
