#!/usr/bin/env python3
"""
Builds data/municipalities.json — a lightweight index of all municipalities
with their state, population, and antenna-derived centroid coordinates.

Reads from:
  - data/population.json   (IBGE population data)
  - data/antennas/*.json   (per-state antenna files)

Run after anatel.py and ibge.py.
"""

import html
import json
import re
import sys
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ANTENNAS_DIR = DATA_DIR / "antennas"
POPULATION_PATH = DATA_DIR / "population.json"
OUT_PATH = DATA_DIR / "municipalities.json"

# ANATEL → IBGE name discrepancies (key can be "Name" or "Name|UF")
NAME_ALIASES: dict[str, str] = {
    "Amparo de São Francisco": "Amparo do São Francisco",
    "Augusto Severo": "Campo Grande",
    "Barão de Monte Alto": "Barão do Monte Alto",
    "Biritiba-Mirim": "Biritiba Mirim",
    "Dona Eusébia": "Dona Euzébia",
    "Florínia": "Florínea",
    "Fortaleza do Tabocão": "Tabocão",
    "Grão Pará": "Grão-Pará",
    "Muquém de São Francisco": "Muquém do São Francisco",
    "Olho-d'Água do Borges": "Olho d'Água do Borges",
    "Passa-Vinte": "Passa Vinte",
    "Santa Teresinha|BA": "Santa Terezinha",  # UF-specific: PB spelling is correct
    "Santo Antônio do Leverger": "Santo Antônio de Leverger",
    "São Luís do Paraitinga": "São Luiz do Paraitinga",
    "São Thomé das Letras": "São Tomé das Letras",
}


def resolve_alias(name: str, uf: str) -> str:
    """Look up alias by name|UF first, then by name alone."""
    return NAME_ALIASES.get(f"{name}|{uf}", NAME_ALIASES.get(name, name))


def normalize_name(s: str) -> str:
    """Normalize for matching: unescape HTML, strip accents, lowercase."""
    s = html.unescape(s)
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)
    return s.lower().strip()


def load_population() -> dict[str, dict]:
    """Load population data keyed by IBGE code."""
    if not POPULATION_PATH.exists():
        print("⚠ data/population.json não encontrado", file=sys.stderr)
        return {}
    data = json.loads(POPULATION_PATH.read_text(encoding="utf-8"))
    return data.get("municipios", {})


def compute_centroids() -> dict[str, dict]:
    """Compute per-municipality centroid from antenna positions.

    Returns: {"normalized_name|uf": {"lat": ..., "lon": ..., "antennas": N, "name": original}}
    """
    centroids: dict[str, dict] = {}

    for path in sorted(ANTENNAS_DIR.glob("*.json")):
        uf = path.stem
        antennas = json.loads(path.read_text(encoding="utf-8"))

        for a in antennas:
            raw_name = html.unescape(a["municipio"])
            name = resolve_alias(raw_name, uf)
            key = normalize_name(f"{name}|{uf}")
            if key not in centroids:
                centroids[key] = {
                    "sum_lat": 0.0,
                    "sum_lon": 0.0,
                    "count": 0,
                    "name": name,
                }
            centroids[key]["sum_lat"] += a["lat"]
            centroids[key]["sum_lon"] += a["lon"]
            centroids[key]["count"] += 1

    result = {}
    for key, c in centroids.items():
        result[key] = {
            "lat": round(c["sum_lat"] / c["count"], 4),
            "lon": round(c["sum_lon"] / c["count"], 4),
            "antennas": c["count"],
            "name": c["name"],
        }
    return result


def main() -> None:
    pop_data = load_population()
    centroids = compute_centroids()

    # Build normalized lookup for population
    pop_norm: dict[str, tuple[str, dict]] = {}
    for ibge_id, info in pop_data.items():
        nk = normalize_name(f"{info['nome']}|{info['uf']}")
        pop_norm[nk] = (ibge_id, info)

    # Build index keyed by IBGE code
    index: dict[str, dict] = {}
    matched_centroids: set[str] = set()

    for nk, (ibge_id, info) in pop_norm.items():
        centroid = centroids.get(nk, {})
        if centroid:
            matched_centroids.add(nk)

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
    for nk, centroid in centroids.items():
        if nk not in matched_centroids:
            name = centroid["name"]
            uf = nk.rsplit("|", 1)[1].upper()
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
    unmatched = [k for k in centroids if k not in matched_centroids]
    print(
        f"data/municipalities.json: {len(index)} municípios "
        f"({with_coords} com coordenadas, {len(unmatched)} sem pop.)",
        file=sys.stderr,
    )
    if unmatched:
        for k in sorted(unmatched):
            c = centroids[k]
            print(f"  ⚠ {c['name']}|{k.rsplit('|',1)[1].upper()}: "
                  f"{c['antennas']} antenas, sem dados IBGE", file=sys.stderr)


if __name__ == "__main__":
    main()
