#!/usr/bin/env python3
"""
Fetches official population estimates from IBGE for all Brazilian
municipalities and writes data/population.json.

Uses the IBGE SIDRA (Agregados) API for bulk per-state queries — 27
requests instead of ~5,570.

Source: IBGE – Estimativas da população residente (tabela 6579).
"""

import gzip
import json
import sys
import urllib.request
from pathlib import Path

# SIDRA Agregados: tabela 6579 (estimativa pop), variável 9324
SIDRA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
    "/periodos/-1/variaveis/9324"
    "?localidades=N6[N3[{state_id}]]"
)

STATES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

OUT_PATH = Path(__file__).parent.parent / "data" / "population.json"


def fetch_json(url: str):
    """Fetch JSON from IBGE, handling their automatic gzip."""
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def fetch_states() -> list[dict]:
    """Return list of {id, sigla, nome} for all Brazilian states."""
    return fetch_json(STATES_URL)


def fetch_population_for_state(state_id: int) -> dict[str, tuple[int, str, str]]:
    """Fetch population for all municipalities in a state via SIDRA.

    Returns: {ibge_id: (population, year, name)}
    """
    data = fetch_json(SIDRA_URL.format(state_id=state_id))
    result: dict[str, tuple[int, str, str]] = {}

    for variable in data:
        for res_block in variable.get("resultados", []):
            for series in res_block.get("series", []):
                loc = series["localidade"]
                ibge_id = loc["id"]
                # Name comes as "Cidade - UF"; strip the " - UF" suffix
                raw_name = loc["nome"]
                name = raw_name.rsplit(" - ", 1)[0] if " - " in raw_name else raw_name

                serie = series["serie"]
                if not serie:
                    continue
                year = max(serie.keys())
                try:
                    pop = int(serie[year])
                except (ValueError, TypeError):
                    continue
                result[ibge_id] = (pop, year, name)

    return result


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Buscando estados...", file=sys.stderr)
    states = sorted(fetch_states(), key=lambda s: s["sigla"])

    all_municipalities: dict[str, dict] = {}
    sample_year = ""
    total = 0

    for state in states:
        sid, uf, sname = state["id"], state["sigla"], state["nome"]
        print(f"  {uf} ({sname})...", end=" ", file=sys.stderr, flush=True)
        try:
            pop_data = fetch_population_for_state(sid)
            for ibge_id, (pop, year, name) in pop_data.items():
                all_municipalities[ibge_id] = {
                    "nome": name,
                    "uf": uf,
                    "populacao": pop,
                    "ano": year,
                }
                sample_year = year
            print(f"{len(pop_data)} municípios", file=sys.stderr)
            total += len(pop_data)
        except Exception as exc:
            print(f"ERRO: {exc}", file=sys.stderr)

    payload = {
        "fonte": f"IBGE – Estimativas da população residente ({sample_year})",
        "url": "https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html",
        "municipios": all_municipalities,
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT_PATH.write_text(out, encoding="utf-8")
    print(
        f"\ndata/population.json gerado com {total} municípios.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
