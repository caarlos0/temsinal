#!/usr/bin/env python3
"""
Builds data/municipalities.json — a lightweight index of all municipalities
with their state, population, and antenna-derived centroid coordinates.

Reads from:
  - data/population.json   (IBGE population data)
  - data/antennas/*.json   (per-state antenna files)

Run after anatel.py and ibge.py.
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ANTENNAS_DIR = DATA_DIR / "antennas"
POPULATION_PATH = DATA_DIR / "population.json"
OUT_PATH = DATA_DIR / "municipalities.json"


def load_population() -> dict[str, dict]:
    """Load population data keyed by IBGE code."""
    if not POPULATION_PATH.exists():
        print("⚠ data/population.json não encontrado", file=sys.stderr)
        return {}
    data = json.loads(POPULATION_PATH.read_text(encoding="utf-8"))
    return data.get("municipios", {})


def compute_centroids() -> dict[str, dict]:
    """Compute per-municipality centroid from antenna positions.

    Returns: {"Município Name|UF": {"lat": ..., "lon": ..., "antennas": N}}
    """
    centroids: dict[str, dict] = {}

    for path in sorted(ANTENNAS_DIR.glob("*.json")):
        uf = path.stem
        antennas = json.loads(path.read_text(encoding="utf-8"))

        for a in antennas:
            key = f"{a['municipio']}|{uf}"
            if key not in centroids:
                centroids[key] = {"sum_lat": 0.0, "sum_lon": 0.0, "count": 0}
            centroids[key]["sum_lat"] += a["lat"]
            centroids[key]["sum_lon"] += a["lon"]
            centroids[key]["count"] += 1

    result = {}
    for key, c in centroids.items():
        result[key] = {
            "lat": round(c["sum_lat"] / c["count"], 4),
            "lon": round(c["sum_lon"] / c["count"], 4),
            "antennas": c["count"],
        }
    return result


def main() -> None:
    pop_data = load_population()
    centroids = compute_centroids()

    # Build index keyed by IBGE code
    index: dict[str, dict] = {}

    for ibge_id, info in pop_data.items():
        name = info["nome"]
        uf = info["uf"]
        key = f"{name}|{uf}"
        centroid = centroids.get(key, {})

        entry: dict = {
            "nome": name,
            "uf": uf,
            "populacao": info["populacao"],
        }
        if "lat" in centroid:
            entry["lat"] = centroid["lat"]
            entry["lon"] = centroid["lon"]
            entry["antenas"] = centroid["antennas"]

        index[ibge_id] = entry

    # Also add municipalities that have antennas but aren't in population data
    pop_names = {f"{v['nome']}|{v['uf']}" for v in pop_data.values()}
    for key, centroid in centroids.items():
        if key not in pop_names:
            name, uf = key.rsplit("|", 1)
            # Find an unused key (won't have proper IBGE code)
            index[f"unknown-{name}-{uf}"] = {
                "nome": name,
                "uf": uf,
                "lat": centroid["lat"],
                "lon": centroid["lon"],
                "antenas": centroid["antennas"],
            }

    out = json.dumps(index, ensure_ascii=False)
    OUT_PATH.write_text(out, encoding="utf-8")

    with_coords = sum(1 for v in index.values() if "lat" in v)
    print(
        f"data/municipalities.json: {len(index)} municípios "
        f"({with_coords} com coordenadas)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
