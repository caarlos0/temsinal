#!/usr/bin/env python3
"""
Generate a PMTiles file from per-state antenna data.

Reads per-state JSON files from data/antennas/, aggregates antennas
into unique sites (lat/lon rounded to 3 decimals), exports GeoJSON,
then runs tippecanoe to produce a PMTiles file.

Usage:
    uv run updater/pmtiles.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ANTENNAS_DIR = DATA_DIR / "antennas"
OUTPUT = DATA_DIR / "towers.pmtiles"

TECH_PRIORITY = ["5G", "4G", "3G", "2G"]


def best_tech(a: str, b: str) -> str:
    ai = TECH_PRIORITY.index(a) if a in TECH_PRIORITY else 99
    bi = TECH_PRIORITY.index(b) if b in TECH_PRIORITY else 99
    return a if ai <= bi else b


def main() -> None:
    state_files = sorted(ANTENNAS_DIR.glob("*.json"))
    if not state_files:
        print("No antenna files found in data/antennas/", file=sys.stderr)
        sys.exit(1)

    # Aggregate into unique sites
    sites: dict[str, dict] = {}
    total = 0

    for path in state_files:
        antennas = json.loads(path.read_text(encoding="utf-8"))
        total += len(antennas)
        for a in antennas:
            key = f"{a['lat']:.3f},{a['lon']:.3f}"
            if key not in sites:
                sites[key] = {
                    "lat": a["lat"],
                    "lon": a["lon"],
                    "tech": a["tecnologia"],
                    "techs": set(),
                    "ops": set(),
                    "municipio": a["municipio"],
                    "uf": a.get("uf", path.stem),
                    "nova": False,
                    "data": None,
                }
            s = sites[key]
            s["tech"] = best_tech(s["tech"], a["tecnologia"])
            s["techs"].add(a["tecnologia"])
            s["ops"].add(a["operadora"])
            if a.get("nova"):
                s["nova"] = True
                if not s["data"] or a.get("data", "") > s["data"]:
                    s["data"] = a.get("data")

    print(f"{total:,} antennas → {len(sites):,} unique sites", file=sys.stderr)

    # Write GeoJSON to temp file
    features = []
    for s in sites.values():
        techs_sorted = [t for t in TECH_PRIORITY if t in s["techs"]]
        ops_sorted = sorted(s["ops"])
        props = {
            "tech": s["tech"],
            "techs": ",".join(techs_sorted),
            "ops": ",".join(ops_sorted),
            "municipio": s["municipio"],
            "uf": s["uf"],
        }
        # Boolean flags for efficient filtering
        for t in TECH_PRIORITY:
            props[f"has_{t.lower()}"] = t in s["techs"]
        for op in ["Vivo", "Claro", "TIM"]:
            props[f"has_{op.lower()}"] = op in s["ops"]
        if s["nova"]:
            props["nova"] = True
            if s["data"]:
                props["data"] = s["data"]

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [s["lon"], s["lat"]],
                },
                "properties": props,
            }
        )

    geojson = {"type": "FeatureCollection", "features": features}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".geojson", delete=False, encoding="utf-8"
    ) as f:
        json.dump(geojson, f, ensure_ascii=False)
        geojson_path = f.name

    print(f"GeoJSON written to {geojson_path}", file=sys.stderr)

    # Run tippecanoe
    cmd = [
        "tippecanoe",
        "-o",
        str(OUTPUT),
        "-z",
        "14",  # max zoom
        "-Z",
        "2",  # min zoom
        "-l",
        "towers",  # layer name
        "-r1",  # don't drop any features at max zoom
        "--drop-densest-as-needed",  # thin at lower zooms only
        "--extend-zooms-if-still-dropping",
        "--force",  # overwrite
        geojson_path,
    ]

    print(f"Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"tippecanoe failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Output: {OUTPUT} ({size_mb:.1f} MB)", file=sys.stderr)

    # Clean up
    Path(geojson_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
