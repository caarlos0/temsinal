#!/usr/bin/env python3
"""
Fetches official population estimates from IBGE for each municipality in
antennamap and writes population.json to the project root.

Source: IBGE – Estimativas da população residente (indicator 29171).
Run this script whenever the municipality list in fetch.py changes or when
you want to refresh the estimates (IBGE publishes new estimates annually).
"""

import gzip
import json
import sys
import urllib.request
from pathlib import Path

from fetch import MUNICIPALITIES

IBGE_INDICATOR = 29171  # "Estimativa da população residente"
OUT_PATH = Path(__file__).parent.parent / "population.json"


def fetch_population(ibge_id: str) -> tuple[int, str]:
    """Return (population, year) for the most recent estimate available."""
    url = (
        f"https://servicodados.ibge.gov.br/api/v1"
        f"/pesquisas/indicadores/{IBGE_INDICATOR}/resultados/{ibge_id}"
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read()

    # IBGE always returns gzip regardless of Accept-Encoding
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))

    estimates: dict[str, str] = data[0]["res"][0]["res"]
    year = max(estimates.keys())
    return int(estimates[year]), year


def main() -> None:
    result: dict[str, dict] = {}
    sample_year: str = ""

    for ibge_id, name in MUNICIPALITIES:
        print(f"  {name} ({ibge_id})...", end=" ", file=sys.stderr, flush=True)
        try:
            pop, year = fetch_population(ibge_id)
            result[name] = {"ibge_id": ibge_id, "populacao": pop, "ano": year}
            sample_year = year
            print(f"{pop:,} hab ({year})", file=sys.stderr)
        except Exception as exc:
            print(f"ERRO: {exc}", file=sys.stderr)

    payload = {
        "fonte": f"IBGE – Estimativas da população residente ({sample_year})",
        "url": "https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html",
        "municipios": result,
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT_PATH.write_text(out, encoding="utf-8")
    print(f"\npopulation.json gerado com {len(result)} municípios.", file=sys.stderr)


if __name__ == "__main__":
    main()
