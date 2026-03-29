#!/usr/bin/env python3
"""
Downloads ANATEL antenna licensing data for all Brazilian states
and outputs per-state JSON files in data/antennas/.

Usage:
    uv run anatel.py              # Fetch all states
    uv run anatel.py --uf PR SP   # Fetch specific states
    uv run anatel.py --resume     # Skip states with existing output files
"""

import argparse
import csv
import gzip
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
IBGE_MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
)

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
    "TIM S A": "TIM",
}

ALL_UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_DELAY = 1
COOKIE_REFRESH_EVERY = 200


# ── IBGE helpers ─────────────────────────────────────────────────────────────


def fetch_ibge_json(url: str):
    """Fetch JSON from IBGE, handling their automatic gzip."""
    with request.urlopen(url, timeout=30) as resp:
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def fetch_municipalities(uf: str) -> list[tuple[str, str]]:
    """Fetch municipalities for a state from IBGE.

    Returns sorted list of (ibge_code, name).
    """
    data = fetch_ibge_json(IBGE_MUNICIPALITIES_URL.format(uf=uf))
    result = [(str(m["id"]), m["nome"]) for m in data]
    result.sort(key=lambda x: x[1])
    return result


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


def request_csv_export(cookie: str, uf: str, ibge_code: str) -> str:
    params = parse.urlencode({
        "skip": "0",
        "filter": "-1",
        "rpp": "50",
        "wfid": "licencas",
        "view": "0",
        "fa_gsearch": "3",
        "fa_uf": uf,
        "fa_municipio": ibge_code,
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
    with request.urlopen(req, timeout=60) as resp:
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
    with request.urlopen(req, timeout=120) as resp:
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


def fetch_with_retry(cookie: str, uf: str, ibge_code: str) -> list[dict]:
    """Fetch CSV from ANATEL with retry + exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            file_path = request_csv_export(cookie, uf, ibge_code)
            return download_csv(cookie, file_path)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_DELAY * (2 ** attempt)
            print(
                f"    Erro (tentativa {attempt + 1}): {e}. "
                f"Retentando em {delay}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
    return []  # unreachable


def rows_to_antennas(rows: list[dict], municipio: str, seen: set) -> list[dict]:
    """Convert ANATEL CSV rows to antenna dicts, deduplicating via seen set."""
    one_year_ago = date.today() - timedelta(days=365)
    antennas = []

    for row in rows:
        entity = normalize_entity(row.get("NomeEntidade", ""))
        raw_tech = normalize(row.get("Tecnologia", ""))
        lat_s = normalize(row.get("Latitude", ""))
        lon_s = normalize(row.get("Longitude", ""))
        date_s = normalize(row.get("DataPrimeiroLicenciamento", ""))

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
            "operadora": html.escape(entity),
            "tecnologia": tech,
            "municipio": html.escape(municipio),
            "lat": lat,
            "lon": lon,
            "data": date_fmt,
            "nova": new_antenna,
        })

    return antennas


# ── Per-state fetching ───────────────────────────────────────────────────────


def fetch_state(
    cookie: str,
    uf: str,
    municipalities: list[tuple[str, str]],
) -> tuple[list[dict], int]:
    """Fetch all antennas for a state, municipality by municipality.

    Returns (antennas, requests_made).
    """
    seen: set[tuple] = set()
    state_antennas: list[dict] = []
    errors = 0

    for i, (ibge_code, name) in enumerate(municipalities, 1):
        print(
            f"  [{i}/{len(municipalities)}] {name} ({ibge_code})...",
            end=" ", file=sys.stderr, flush=True,
        )
        try:
            rows = fetch_with_retry(cookie, uf, ibge_code)
            antennas = rows_to_antennas(rows, name, seen)
            print(
                f"{len(rows)} registros → {len(antennas)} antenas",
                file=sys.stderr,
            )
            state_antennas.extend(antennas)
        except Exception as e:
            print(f"ERRO: {e}", file=sys.stderr)
            errors += 1

        time.sleep(REQUEST_DELAY)

    if errors:
        print(
            f"  ⚠ {errors} município(s) com erro em {uf}",
            file=sys.stderr,
        )

    return state_antennas, len(municipalities)


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
    requests_since_refresh = 0

    for state_idx, uf in enumerate(target_ufs, 1):
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(
            f"[{state_idx}/{len(target_ufs)}] Buscando municípios de {uf}...",
            file=sys.stderr,
        )

        municipalities = fetch_municipalities(uf)
        print(f"  {len(municipalities)} municípios", file=sys.stderr)

        # Refresh session cookie periodically
        if requests_since_refresh >= COOKIE_REFRESH_EVERY:
            print("Renovando sessão ANATEL...", file=sys.stderr)
            try:
                cookie = get_session_cookie()
                requests_since_refresh = 0
            except Exception as e:
                print(f"  Aviso: {e}", file=sys.stderr)

        state_antennas, reqs = fetch_state(cookie, uf, municipalities)
        requests_since_refresh += reqs

        out_path = DATA_DIR / f"{uf}.json"
        out = json.dumps(state_antennas, ensure_ascii=False)
        out_path.write_text(out, encoding="utf-8")

        size_kb = len(out.encode()) / 1024
        print(
            f"\n  {uf}: {len(state_antennas)} antenas — {size_kb:.1f} KB",
            file=sys.stderr,
        )
        grand_total += len(state_antennas)

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(
        f"Total: {grand_total} antenas em {len(target_ufs)} estados",
        file=sys.stderr,
    )
    print(f"Arquivos em {DATA_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
