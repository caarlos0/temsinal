#!/usr/bin/env python3
"""
Builds data/municipalities.json — a lightweight index of all municipalities
with their state, population, and antenna-derived centroid coordinates.

Reads from:
  - data/population.json   (IBGE population data)
  - data/antennas/*.json   (per-state antenna files, with IBGE codes)

Run after anatel.py and ibge.py.
"""

import html
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

    Returns: {"ibge_code": {"lat": ..., "lon": ..., "antennas": N, "name": ..., "uf": ...}}
    """
    centroids: dict[str, dict] = {}

    for path in sorted(ANTENNAS_DIR.glob("*.json")):
        uf = path.stem
        antennas = json.loads(path.read_text(encoding="utf-8"))

        for a in antennas:
            ibge = a.get("ibge")
            if not ibge:
                continue
            if ibge not in centroids:
                centroids[ibge] = {
                    "sum_lat": 0.0,
                    "sum_lon": 0.0,
                    "count": 0,
                    "name": html.unescape(a["municipio"]),
                    "uf": uf,
                }
            centroids[ibge]["sum_lat"] += a["lat"]
            centroids[ibge]["sum_lon"] += a["lon"]
            centroids[ibge]["count"] += 1

    return {
        ibge: {
            "lat": round(c["sum_lat"] / c["count"], 4),
            "lon": round(c["sum_lon"] / c["count"], 4),
            "antennas": c["count"],
            "name": c["name"],
            "uf": c["uf"],
        }
        for ibge, c in centroids.items()
    }


def main() -> None:
    pop_data = load_population()
    centroids = compute_centroids()

    # Build index keyed by IBGE code
    index: dict[str, dict] = {}

    for ibge_id, info in pop_data.items():
        centroid = centroids.get(ibge_id, {})

        entry: dict = {
            "nome": info["nome"],
            "uf": info["uf"],
            "populacao": info["populacao"],
        }
        if "lat" in centroid:
            entry["lat"] = centroid["lat"]
            entry["lon"] = centroid["lon"]
            entry["antenas"] = centroid["antennas"]

        index[ibge_id] = entry

    # Also add municipalities that have antennas but aren't in population data
    for ibge_id, centroid in centroids.items():
        if ibge_id not in index:
            index[ibge_id] = {
                "nome": centroid["name"],
                "uf": centroid["uf"],
                "lat": centroid["lat"],
                "lon": centroid["lon"],
                "antenas": centroid["antennas"],
            }

    out = json.dumps(index, ensure_ascii=False, indent=2)
    OUT_PATH.write_text(out, encoding="utf-8")

    with_coords = sum(1 for v in index.values() if "lat" in v)
    without_pop = [k for k in centroids if k not in pop_data]
    print(
        f"data/municipalities.json: {len(index)} municípios "
        f"({with_coords} com coordenadas, {len(without_pop)} sem pop.)",
        file=sys.stderr,
    )
    for ibge_id in sorted(without_pop):
        c = centroids[ibge_id]
        print(f"  ⚠ {c['name']}|{c['uf']} ({ibge_id}): "
              f"{c['antennas']} antenas, sem dados IBGE", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.", file=sys.stderr)
        sys.exit(130)
