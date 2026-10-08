"""Build CourtMate's Philippine location seed files from PSGC JSON.

The Philippine Standard Geographic Code (PSGC) is published by the Philippine
Statistics Authority. This script converts the JSON rendering served by the
open PSGC API (https://psgc.gitlab.io/api/) into the compact CSV files that
`app.seed` loads into the geo_* tables.

Usage:
    python scripts/build_psgc.py --download /tmp/psgc_raw   # fetch + build
    python scripts/build_psgc.py /tmp/psgc_raw              # build from existing JSON

Only the standard library is used so it can run with any Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

API_BASE = "https://psgc.gitlab.io/api"
SOURCES = ("regions", "provinces", "cities-municipalities", "barangays")
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "psgc"


def download(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        url = f"{API_BASE}/{name}.json"
        print(f"fetching {url}")
        with urllib.request.urlopen(url, timeout=180) as response:
            (raw_dir / f"{name}.json").write_bytes(response.read())


def load(raw_dir: Path, name: str) -> list[dict]:
    with (raw_dir / f"{name}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: Path, header: list[str], rows: list[list[str]], compress: bool = False) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    payload = buffer.getvalue().encode("utf-8")
    if compress:
        # mtime=0 keeps the archive byte-identical between runs.
        with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as archive:
            archive.write(payload)
    else:
        path.write_bytes(payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(raw_dir: Path) -> None:
    regions = load(raw_dir, "regions")
    provinces = load(raw_dir, "provinces")
    cities = load(raw_dir, "cities-municipalities")
    barangays = load(raw_dir, "barangays")

    region_codes = {item["code"] for item in regions}
    province_codes = {item["code"] for item in provinces}
    city_codes = {item["code"] for item in cities}

    region_rows = sorted([r["code"], r["name"], r["regionName"], r["islandGroupCode"]] for r in regions)
    province_rows = sorted([p["code"], p["name"], p["regionCode"]] for p in provinces)

    city_rows = []
    for city in cities:
        # Highly urbanized and independent cities (and all of NCR) have no province.
        province = city["provinceCode"] or ""
        if province and province not in province_codes:
            raise SystemExit(f"city {city['code']} references unknown province {province}")
        if city["regionCode"] not in region_codes:
            raise SystemExit(f"city {city['code']} references unknown region {city['regionCode']}")
        city_rows.append([city["code"], city["name"], city["regionCode"], province, "1" if city["isCity"] else "0"])
    city_rows.sort()

    barangay_rows = []
    for barangay in barangays:
        parent = barangay["cityCode"] or barangay["municipalityCode"]
        if parent not in city_codes:
            raise SystemExit(f"barangay {barangay['code']} references unknown city/municipality {parent}")
        barangay_rows.append([barangay["code"], barangay["name"], parent])
    barangay_rows.sort()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checksums = {
        "regions.csv": write_csv(OUT_DIR / "regions.csv", ["code", "name", "region_name", "island_group"], region_rows),
        "provinces.csv": write_csv(OUT_DIR / "provinces.csv", ["code", "name", "region_code"], province_rows),
        "cities.csv": write_csv(OUT_DIR / "cities.csv", ["code", "name", "region_code", "province_code", "is_city"], city_rows),
        "barangays.csv.gz": write_csv(OUT_DIR / "barangays.csv.gz", ["code", "name", "city_code"], barangay_rows, compress=True),
    }
    manifest = {
        "source": API_BASE,
        "publisher": "Philippine Statistics Authority (PSGC), via the open PSGC API",
        "retrieved": date.today().isoformat(),
        "counts": {
            "regions": len(region_rows),
            "provinces": len(province_rows),
            "citiesMunicipalities": len(city_rows),
            "barangays": len(barangay_rows),
        },
        "sha256": checksums,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_dir", type=Path, help="directory holding the PSGC JSON files")
    parser.add_argument("--download", action="store_true", help="fetch the JSON files into raw_dir first")
    args = parser.parse_args()
    if args.download:
        download(args.raw_dir)
    build(args.raw_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
