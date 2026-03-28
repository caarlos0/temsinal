#!/usr/bin/env python3
"""
Downloads ANATEL antenna licensing data for Marechal Cândido Rondon (PR)
and neighboring municipalities, converting to antennas.json for index.html.
"""

import csv
import io
import json
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib import request, parse

BASE_URL = "https://sistemas.anatel.gov.br/se/public/view/b"

MUNICIPALITIES = [
    # Already in
    ("4114609", "Marechal Cândido Rondon"),
    ("4115853", "Mercedes"),
    ("4117222", "Nova Santa Rosa"),
    ("4118451", "Pato Bragado"),
    ("4120853", "Quatro Pontes"),
    # Explicitly requested
    ("4127700", "Toledo"),
    ("4104808", "Cascavel"),
    ("4108809", "Guaíra"),
    ("4127403", "Terra Roxa"),
    # Guaíra → Cascavel corridor
    ("4117909", "Palotina"),
    ("4123501", "Santa Helena"),
    ("4115358", "Maripá"),
    ("4107538", "Entre Rios do Oeste"),
    ("4125456", "São José das Palmeiras"),
    ("4107157", "Diamante D'Oeste"),
    ("4125753", "São Pedro do Iguaçu"),
    ("4128559", "Vera Cruz do Oeste"),
    ("4117453", "Ouro Verde do Oeste"),
    ("4127957", "Tupãssi"),
    ("4112751", "Jesuítas"),
    ("4108205", "Formosa do Oeste"),
    ("4102000", "Assis Chateaubriand"),
    ("4116703", "Nova Aurora"),
    ("4103453", "Cafelândia"),
    ("4106308", "Corbélia"),
    ("4105003", "Catanduvas"),
    ("4104600", "Capitão Leônidas Marques"),
    ("4109302", "Guaraniaçu"),
    ("4109757", "Ibema"),
    ("4103354", "Braganey"),
    ("4101051", "Anahy"),
]

# Technologies shown to end users — infrastructure-only types are excluded
USER_FACING_TECH = {"5G", "4G", "3G", "2G"}

TECH_MAP = {
    "NR": "5G",
    "LTE": "4G",
    "WCDMA": "3G",
    "GSM": "2G",
}


def infer_tech(row: dict) -> str:
    """Guess technology from DesignacaoEmissao and FreqTxMHz when Tecnologia is blank."""
    desig = row.get("DesignacaoEmissao", "").strip().strip('"')
    freq_s = row.get("FreqTxMHz", "").strip().strip('"')

    try:
        freq = float(freq_s)
    except ValueError:
        freq = 0.0

    # Wide-band digital microwave (D7W / G7W) at > 1 GHz → backhaul link
    if freq > 1000 and ("D7W" in desig or "G7W" in desig or "Q7W" in desig):
        return "Backhaul"

    # Narrowband VHF/UHF emissions → land mobile / trunked radio
    narrow = ("F1E" in desig or "F1D" in desig or "F1W" in desig or
              "F3E" in desig or "F2D" in desig)
    if narrow and freq < 500:
        return "Radio"

    return "?"


def get_session_cookie() -> str:
    req = request.Request(f"{BASE_URL}/licenciamento.php")
    with request.urlopen(req) as resp:
        for header, value in resp.headers.items():
            if header.lower() == "set-cookie" and "PHPSESSID" in value:
                return value.split(";")[0]
    raise RuntimeError("Could not obtain session cookie")


def request_csv_export(cookie: str, ibge_code: str) -> str:
    params = parse.urlencode({
        "skip": "0",
        "filter": "-1",
        "rpp": "50",
        "wfid": "licencas",
        "view": "0",
        "fa_gsearch": "3",
        "fa_uf": "PR",
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
    with request.urlopen(req) as resp:
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
    with request.urlopen(req) as resp:
        raw = resp.read()

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
        content = zf.read(name).decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    return list(reader)


def normalize(value: str) -> str:
    return value.strip().strip('"')


ENTITY_ALIASES = {
    "TELEFÔNICA BRASIL S.A.": "Vivo",
    "TELEFONICA BRASIL S.A.": "Vivo",
    "Telefonica Brasil S.a.": "Vivo",
    "CLARO S.A.": "Claro",
    "TIM S A": "TIM",
}


def normalize_entity(name: str) -> str:
    name = normalize(name)
    return ENTITY_ALIASES.get(name, name)


def to_json(rows: list[dict], municipio: str, seen: set) -> list[dict]:
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
            "operadora": entity,
            "tecnologia": tech,
            "municipio": municipio,
            "lat": lat,
            "lon": lon,
            "data": date_fmt,
            "nova": new_antenna,
        })

    return antennas


def main():
    print("Obtendo sessão...", file=sys.stderr)
    cookie = get_session_cookie()

    seen: set[tuple] = set()
    all_antennas = []

    for ibge_code, name in MUNICIPALITIES:
        print(f"Baixando {name} ({ibge_code})...", file=sys.stderr)
        file_path = request_csv_export(cookie, ibge_code)
        rows = download_csv(cookie, file_path)
        antennas = to_json(rows, name, seen)
        print(f"  {len(rows)} registros → {len(antennas)} antenas únicas", file=sys.stderr)
        all_antennas.extend(antennas)

    print(f"\nTotal: {len(all_antennas)} antenas", file=sys.stderr)

    out_path = Path(__file__).parent.parent / "antennas.json"
    out = json.dumps(all_antennas, ensure_ascii=False, indent=2)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)

    print("antennas.json gerado com sucesso.", file=sys.stderr)


if __name__ == "__main__":
    main()
