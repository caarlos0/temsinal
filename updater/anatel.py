#!/usr/bin/env python3
"""
Downloads ANATEL antenna licensing data for all Brazilian states
and outputs per-state JSON files in data/antennas/.

Uses per-state bulk export (fa_gsearch=2) — one request per state
instead of one per municipality.

Usage:
    uv run anatel.py              # Fetch all states
    uv run anatel.py --uf PR SP   # Fetch specific states
    uv run anatel.py --resume     # Skip states with existing output files
"""

import argparse
import csv
import html
import io
import json
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib import request, parse

BASE_URL = "https://sistemas.anatel.gov.br/se/public/view/b"

DATA_DIR = Path(__file__).parent.parent / "data" / "antennas"

USER_FACING_TECH = {"5G", "4G", "3G", "2G"}

TECH_MAP = {
    "NR": "5G",
    "LTE": "4G",
    "WCDMA": "3G",
    "GSM": "2G",
}

ENTITY_ALIASES = {
    "TELEFÔNICA BRASIL S.A.": "Vivo",
    "TELEFONICA BRASIL S.A.": "Vivo",
    "Telefonica Brasil S.a.": "Vivo",
    "CLARO S.A.": "Claro",
    "Claro S.A.": "Claro",
    "TIM S A": "TIM",
    "TIM S/A": "TIM",
}

# Only include antennas from the 3 major cell phone carriers
ALLOWED_OPERATORS = {"Vivo", "Claro", "TIM"}

ALL_UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_DELAY = 2


# ── ANATEL helpers ───────────────────────────────────────────────────────────


def infer_tech(row: dict) -> str:
    """Guess technology from DesignacaoEmissao and FreqTxMHz when Tecnologia is blank."""
    desig = row.get("DesignacaoEmissao", "").strip().strip('"')
    freq_s = row.get("FreqTxMHz", "").strip().strip('"')

    try:
        freq = float(freq_s)
    except ValueError:
        freq = 0.0

    if freq > 1000 and ("D7W" in desig or "G7W" in desig or "Q7W" in desig):
        return "Backhaul"

    narrow = ("F1E" in desig or "F1D" in desig or "F1W" in desig or
              "F3E" in desig or "F2D" in desig)
    if narrow and freq < 500:
        return "Radio"

    return "?"


def get_session_cookie() -> str:
    req = request.Request(f"{BASE_URL}/licenciamento.php")
    with request.urlopen(req, timeout=30) as resp:
        for header, value in resp.headers.items():
            if header.lower() == "set-cookie" and "PHPSESSID" in value:
                return value.split(";")[0]
    raise RuntimeError("Could not obtain ANATEL session cookie")


def export_state_csv(cookie: str, uf: str) -> str:
    """Request a CSV export for an entire state. Returns the download path."""
    params = parse.urlencode({
        "skip": "0",
        "filter": "-1",
        "rpp": "50",
        "wfid": "licencas",
        "view": "0",
        "fa_gsearch": "2",
        "fa_uf": uf,
    }).encode()

    req = request.Request(
        f"{BASE_URL}/export_licenciamento.php",
        data=params,
        headers={
            "Cookie": cookie,
            "Referer": f"{BASE_URL}/licenciamento.php",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())

    redirect = body.get("redirectUrl") or body.get("submitUrl")
    if not redirect:
        raise RuntimeError(f"Unexpected export response: {body}")
    return redirect


def download_csv(cookie: str, path: str) -> list[dict]:
    req = request.Request(
        f"https://sistemas.anatel.gov.br{path}",
        headers={"Cookie": cookie},
    )
    with request.urlopen(req, timeout=300) as resp:
        raw = resp.read()

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
        content = zf.read(name).decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    return list(reader)


def normalize(value: str) -> str:
    return value.strip().strip('"')


def normalize_entity(name: str) -> str:
    name = normalize(name)
    return ENTITY_ALIASES.get(name, name)


def rows_to_antennas(rows: list[dict]) -> list[dict]:
    """Convert ANATEL CSV rows to antenna dicts."""
    one_year_ago = date.today() - timedelta(days=365)
    seen: set[tuple] = set()
    antennas = []

    for row in rows:
        entity = normalize_entity(row.get("NomeEntidade", ""))
        if entity not in ALLOWED_OPERATORS:
            continue
        raw_tech = normalize(row.get("Tecnologia", ""))
        lat_s = normalize(row.get("Latitude", ""))
        lon_s = normalize(row.get("Longitude", ""))
        date_s = normalize(row.get("DataPrimeiroLicenciamento", ""))
        municipio = normalize(row.get("Municipio.NomeMunicipio", ""))

        if not lat_s or not lon_s:
            continue

        try:
            lat = float(lat_s)
            lon = float(lon_s)
        except ValueError:
            continue

        tech = TECH_MAP.get(raw_tech) or infer_tech(row)

        if tech not in USER_FACING_TECH:
            continue

        key = (entity, tech, lat, lon)
        if key in seen:
            continue
        seen.add(key)

        new_antenna = False
        if date_s:
            try:
                licensed_date = date.fromisoformat(date_s)
                new_antenna = licensed_date >= one_year_ago
                date_fmt = licensed_date.strftime("%d/%m/%Y")
            except ValueError:
                date_fmt = date_s
        else:
            date_fmt = ""

        antennas.append({
            "operadora": entity,
            "tecnologia": tech,
            "municipio": municipio if municipio else "Desconhecido",
            "lat": lat,
            "lon": lon,
            "data": date_fmt,
            "nova": new_antenna,
        })

    return antennas


def fetch_state_with_retry(cookie: str, uf: str) -> list[dict]:
    """Fetch all rows for a state with retry + exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            file_path = export_state_csv(cookie, uf)
            return download_csv(cookie, file_path)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_DELAY * (2 ** attempt)
            print(
                f"  Erro (tentativa {attempt + 1}): {e}. "
                f"Retentando em {delay}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
    return []  # unreachable


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch ANATEL antenna data for Brazil",
    )
    parser.add_argument(
        "--uf", nargs="*", metavar="UF",
        help="States to fetch (default: all)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip states that already have output files",
    )
    args = parser.parse_args()

    target_ufs = sorted(args.uf) if args.uf else ALL_UFS

    invalid = [uf for uf in target_ufs if uf not in ALL_UFS]
    if invalid:
        print(f"UFs inválidas: {', '.join(invalid)}", file=sys.stderr)
        sys.exit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.resume:
        existing = {p.stem for p in DATA_DIR.glob("*.json")}
        skipped = [uf for uf in target_ufs if uf in existing]
        target_ufs = [uf for uf in target_ufs if uf not in existing]
        if skipped:
            print(
                f"Pulando estados já baixados: {', '.join(skipped)}",
                file=sys.stderr,
            )

    if not target_ufs:
        print("Nenhum estado para buscar.", file=sys.stderr)
        return

    print(f"Estados: {', '.join(target_ufs)}", file=sys.stderr)
    print("Obtendo sessão ANATEL...", file=sys.stderr)
    cookie = get_session_cookie()

    grand_total = 0

    for state_idx, uf in enumerate(target_ufs, 1):
        print(
            f"\n[{state_idx}/{len(target_ufs)}] {uf}...",
            end=" ", file=sys.stderr, flush=True,
        )

        try:
            rows = fetch_state_with_retry(cookie, uf)
            antennas = rows_to_antennas(rows)

            out_path = DATA_DIR / f"{uf}.json"
            out = json.dumps(antennas, ensure_ascii=False)
            out_path.write_text(out, encoding="utf-8")

            size_kb = len(out.encode()) / 1024
            print(
                f"{len(rows)} registros → {len(antennas)} antenas "
                f"({size_kb:.1f} KB)",
                file=sys.stderr,
            )
            grand_total += len(antennas)
        except Exception as e:
            print(f"ERRO: {e}", file=sys.stderr)

        # Refresh cookie every 10 states
        if state_idx % 10 == 0 and state_idx < len(target_ufs):
            try:
                cookie = get_session_cookie()
            except Exception:
                pass

        time.sleep(REQUEST_DELAY)

    print(f"\nTotal: {grand_total} antenas em {len(target_ufs)} estados", file=sys.stderr)
    print(f"Arquivos em {DATA_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
