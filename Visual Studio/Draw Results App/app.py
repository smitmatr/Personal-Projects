from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SPECIES = "sheep"

GAME_ANIMALS = {
    "sheep": {
        "label": "Sheep",
        "slug": "sheephunting",
        "map_sp": "sheep",
        "csv": "sheep_draw_by_area_raw.csv",
    },
    "caribou": {"label": "Caribou", "slug": "caribouhunting", "map_sp": "caribou", "csv": None},
    "moose": {"label": "Moose", "slug": "moosehunting", "map_sp": "moose", "csv": None},
    "brown_bear": {"label": "Brown Bear", "slug": "brownbearhunting", "map_sp": "brownbear", "csv": None},
    "black_bear": {"label": "Black Bear", "slug": "blackbearhunting", "map_sp": "blackbear", "csv": None},
    "mountain_goat": {"label": "Mountain Goat", "slug": "goathunting", "map_sp": "goat", "csv": None},
    "deer": {"label": "Deer", "slug": "deerhunting", "map_sp": "deer", "csv": None},
    "elk": {"label": "Elk", "slug": "elkhunting", "map_sp": "elk", "csv": None},
    "muskox": {"label": "Muskox", "slug": "muskoxhunting", "map_sp": "muskox", "csv": None},
    "bison": {"label": "Bison", "slug": "bisonhunting", "map_sp": "bison", "csv": None},
}

SPECIES_ALIASES = {
    "brown bear": "brown_bear",
    "black bear": "black_bear",
    "mountain goat": "mountain_goat",
}

GMU_INFO_BASE = "https://www.adfg.alaska.gov/index.cfm?adfg=huntingmaps.gmuinfo&gmu={gmu}"
NUMERIC_COLS = ["Year", "Permits", "Hunters", "MaleHarvest", "FemaleHarvest", "TotalHarvest", "SuccessPct"]

LIVE_DATA_TTL_SECONDS = 3600
_OPP_CACHE: dict[str, dict] = {}
_HARVEST_CACHE: dict[str, dict] = {}

# Sheep fallback mapping retained in case opportunities scraping is unavailable.
SHEEP_HUNT_TO_GMUS_FALLBACK = {
    "DS003": ["20"], "DS004": ["20"], "DS024": ["14"], "DS026": ["14"], "DS030": ["19"],
    "DS033": ["14"], "DS036": ["19"], "DS060": ["19"], "DS065": ["13"], "DS102": ["20"],
    "DS103": ["19"], "DS123": ["14"], "DS124": ["14"], "DS125": ["14"], "DS126": ["14"],
    "DS130": ["14", "16"], "DS131": ["14", "16"], "DS132": ["14", "16"], "DS134": ["14", "16"],
    "DS135": ["14", "16"], "DS136": ["14", "16"], "DS137": ["17"], "DS138": ["17"], "DS140": ["14"],
    "DS141": ["14"], "DS150": ["14"], "DS156": ["14"], "DS160": ["13"], "DS165": ["13"], "DS170": ["14"],
    "DS175": ["14"], "DS180": ["14"], "DS185": ["14"], "DS190": ["14"], "DS195": ["14"], "DS203": ["20"],
    "DS204": ["20"], "DS205": ["20"], "DS206": ["20"], "DS207": ["20"], "DS224": ["14", "21"],
    "DS225": ["14"], "DS230": ["14", "23"], "DS231": ["14", "23"], "DS232": ["14", "23"], "DS233": ["14", "23"],
    "DS236": ["14", "24"], "DS237": ["14", "24"], "DS238": ["24"], "DS240": ["14", "24"], "DS241": ["14", "24"],
    "DS260": ["13", "25"], "DS265": ["13", "25"], "DS270": ["14", "25"], "DS275": ["25", "26"],
    "DS280": ["25", "26"], "DS285": ["14", "26"], "DS290": ["25", "26"], "DS295": ["25", "26"],
}


def normalize_species(species: str | None) -> str:
    raw = (species or DEFAULT_SPECIES).strip().lower()
    return SPECIES_ALIASES.get(raw, raw)


def species_config(species: str | None) -> dict:
    key = normalize_species(species)
    return GAME_ANIMALS.get(key, GAME_ANIMALS[DEFAULT_SPECIES])


def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = curl_requests.get(url, impersonate="chrome", timeout=30)
        resp.raise_for_status()
        return resp.text or ""
    except Exception:
        resp = requests.get(url, timeout=30, headers=headers)
        resp.raise_for_status()
        return resp.text or ""


def parse_number(value: str) -> float:
    cleaned = re.sub(r"[^0-9.-]", "", (value or "").strip())
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_success_pct(value: str) -> float | None:
    text = (value or "").strip().lower()
    if not text or "no records" in text:
        return None
    cleaned = re.sub(r"[^0-9.-]", "", text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fallback_sheep_opportunities_lookup() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for hunt, gmus in SHEEP_HUNT_TO_GMUS_FALLBACK.items():
        out[hunt] = {
            "unit_text": f"GMU {'/'.join(gmus)} (fallback mapping)",
            "gmus": gmus,
            "huntfile_id": "",
            "details_url": "",
        }
    return out


def scrape_opportunities_lookup(species: str) -> dict[str, dict]:
    species_key = normalize_species(species)
    cached = _OPP_CACHE.get(species_key)
    now = time.time()
    if cached and (now - float(cached["timestamp"])) < LIVE_DATA_TTL_SECONDS:
        return cached["lookup"]

    config = species_config(species_key)
    slug = config["slug"]
    url = f"https://www.adfg.alaska.gov/index.cfm?adfg={slug}.opportunities&hunttype=D&performsearch=true"

    lookup: dict[str, dict] = {}
    try:
        soup = BeautifulSoup(fetch_html(url), "html.parser")
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue

            hunt_code = cells[0].strip().upper()
            if not re.fullmatch(r"[A-Z]{1,3}\d{3}", hunt_code):
                continue

            unit_text = cells[1].strip()
            gmu_tokens = sorted(set(re.findall(r"\b\d{1,2}[A-E]?\b", unit_text)))
            numeric_gmus = []
            for token in gmu_tokens:
                m = re.match(r"^(\d{1,2})", token)
                if m:
                    numeric_gmus.append(m.group(1))

            huntfile_id = ""
            details_url = ""
            for a in tr.find_all("a", href=True):
                href = a["href"].strip()
                low = href.lower()
                if "hunt_details" in low and "huntfile_id" in low:
                    m = re.search(r"huntfile_id=(\d+)", low)
                    if m:
                        huntfile_id = m.group(1)
                    details_url = href if href.startswith("http") else f"https://www.adfg.alaska.gov{href}"
                    break

            lookup[hunt_code] = {
                "unit_text": unit_text,
                "gmus": sorted(set(numeric_gmus)),
                "huntfile_id": huntfile_id,
                "details_url": details_url,
            }
    except Exception:
        lookup = {}

    if species_key == "sheep" and not lookup:
        lookup = fallback_sheep_opportunities_lookup()

    if not lookup and cached and cached.get("lookup"):
        return cached["lookup"]

    _OPP_CACHE[species_key] = {"timestamp": now, "lookup": lookup}
    return lookup


def scrape_harvest_dataset(species: str) -> pd.DataFrame:
    species_key = normalize_species(species)
    cached = _HARVEST_CACHE.get(species_key)
    now = time.time()
    if cached and (now - float(cached["timestamp"])) < LIVE_DATA_TTL_SECONDS:
        return cached["df"]

    config = species_config(species_key)
    slug = config["slug"]
    base_url = f"https://www.adfg.alaska.gov/index.cfm?adfg={slug}.harvest"

    html = fetch_html(base_url)
    soup = BeautifulSoup(html, "html.parser")

    year_select = soup.find("select", attrs={"name": "year"})
    if not year_select:
        raise FileNotFoundError(f"No harvest data selector found for species '{species_key}'")

    years = []
    for option in year_select.find_all("option"):
        value = (option.get("value") or "").strip()
        if value.isdigit():
            years.append(int(value))

    if not years:
        raise FileNotFoundError(f"No harvest years found for species '{species_key}'")

    rows: list[dict] = []
    for year in sorted(set(years)):
        year_url = f"{base_url}&year={year}&hunttype=d"
        year_soup = BeautifulSoup(fetch_html(year_url), "html.parser")

        table = None
        for candidate in year_soup.find_all("table"):
            headers = [th.get_text(" ", strip=True).lower() for th in candidate.find_all("th")]
            if any("hunt" in h for h in headers) and any("permits" in h for h in headers):
                table = candidate
                break

        if table is None:
            continue

        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 7:
                continue

            hunt_code = cells[0].strip().upper()
            if not re.fullmatch(r"[A-Z]{1,3}\d{3}", hunt_code):
                continue

            rows.append(
                {
                    "Year": year,
                    "HuntCode": hunt_code,
                    "Permits": parse_number(cells[1]),
                    "Hunters": parse_number(cells[2]),
                    "MaleHarvest": parse_number(cells[3]),
                    "FemaleHarvest": parse_number(cells[4]),
                    "TotalHarvest": parse_number(cells[5]),
                    "SuccessPct": parse_success_pct(cells[6]),
                }
            )

    if not rows:
        raise FileNotFoundError(f"No draw-harvest rows found for species '{species_key}'")

    df = pd.DataFrame(rows)
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["HuntCode"] = df["HuntCode"].astype(str).str.strip()
    df = df.sort_values(["HuntCode", "Year"]).reset_index(drop=True)

    _HARVEST_CACHE[species_key] = {"timestamp": now, "df": df}
    return df


def species_csv_path(species: str = DEFAULT_SPECIES) -> Path | None:
    config = species_config(species)
    csv_name = config.get("csv")
    if not csv_name:
        return None
    return BASE_DIR / str(csv_name)


def load_dataset(species: str = DEFAULT_SPECIES) -> pd.DataFrame:
    species_key = normalize_species(species)
    csv_path = species_csv_path(species_key)

    if csv_path is not None and csv_path.exists():
        df = pd.read_csv(csv_path)
        for col in NUMERIC_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["HuntCode"] = df["HuntCode"].astype(str).str.strip()
        return df.sort_values(["HuntCode", "Year"]).reset_index(drop=True)

    return scrape_harvest_dataset(species_key)


def build_series(df: pd.DataFrame, hunt_code: str) -> dict:
    area = df[df["HuntCode"] == hunt_code].copy()
    if area.empty:
        return {"years": [], "permits": [], "hunters": [], "total_harvest": [], "success_pct": []}

    min_year = int(df["Year"].min())
    max_year = int(df["Year"].max())
    all_years = list(range(min_year, max_year + 1))

    area = area.set_index("Year").reindex(all_years).reset_index()
    for col in ["Permits", "Hunters", "MaleHarvest", "FemaleHarvest", "TotalHarvest"]:
        area[col] = area[col].fillna(0)

    return {
        "years": [int(v) for v in area["Year"].fillna(0).tolist()],
        "permits": [float(v) for v in area["Permits"].fillna(0).tolist()],
        "hunters": [float(v) for v in area["Hunters"].fillna(0).tolist()],
        "total_harvest": [float(v) for v in area["TotalHarvest"].fillna(0).tolist()],
        "success_pct": [float(v) if pd.notna(v) else None for v in area["SuccessPct"].tolist()],
    }


def build_draw_odds_series(df: pd.DataFrame, hunt_code: str) -> dict:
    area = df[df["HuntCode"] == hunt_code].copy()
    if area.empty:
        return {"years": [], "applicants": [], "draw_odds_pct": []}

    min_year = int(df["Year"].min())
    max_year = int(df["Year"].max())
    all_years = list(range(min_year, max_year + 1))

    area = area.set_index("Year").reindex(all_years).reset_index()

    if "Applicants" in area.columns:
        applicants = area["Applicants"].fillna(0)
    else:
        applicants = area.get("Hunters", pd.Series([0] * len(area))).fillna(0)

    permits = area.get("Permits", pd.Series([0] * len(area))).fillna(0)
    success = area.get("SuccessPct", pd.Series([None] * len(area)))

    draw_odds = []
    for idx, applicant_total in enumerate(applicants.tolist()):
        applicant_value = float(applicant_total) if pd.notna(applicant_total) else 0.0
        if applicant_value > 0:
            permit_value = float(permits.iloc[idx]) if pd.notna(permits.iloc[idx]) else 0.0
            draw_odds.append((permit_value / applicant_value) * 100.0)
        elif pd.notna(success.iloc[idx]):
            draw_odds.append(float(success.iloc[idx]))
        else:
            draw_odds.append(None)

    return {
        "years": [int(v) for v in area["Year"].fillna(0).tolist()],
        "applicants": [float(v) for v in applicants.tolist()],
        "draw_odds_pct": [float(v) if v is not None and pd.notna(v) else None for v in draw_odds],
    }


def gmu_to_hunts_from_lookup(lookup: dict[str, dict]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for hunt_code, info in lookup.items():
        for gmu in info.get("gmus", []) or []:
            mapping.setdefault(str(gmu), []).append(hunt_code)

    for gmu in list(mapping.keys()):
        mapping[gmu] = sorted(set(mapping[gmu]))

    return mapping


def get_species_gmu_mapping(species: str) -> dict[str, list[str]]:
    lookup = scrape_opportunities_lookup(species)
    mapping = gmu_to_hunts_from_lookup(lookup)

    if mapping:
        return mapping

    # If opportunities are temporarily unavailable, keep the app testable by grouping
    # all live hunt codes under a single synthetic bucket.
    try:
        df = load_dataset(species)
    except Exception:
        return {}

    all_hunts = sorted(df["HuntCode"].dropna().astype(str).str.strip().unique().tolist())
    if not all_hunts:
        return {}
    return {"All": all_hunts}


def draw_map_url(species: str, hunt_code: str, gmus: list[str] | None = None) -> str:
    if gmus:
        clean = sorted({str(g).strip() for g in gmus if str(g).strip()})
        if clean:
            return GMU_INFO_BASE.format(gmu=clean[0])

    sp = species_config(species).get("map_sp", "sheep")
    return f"https://www.adfg.alaska.gov/index.cfm?adfg=hunting.largehuntmap&sp={sp}&hunt={hunt_code.lower()}"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/species")
def species_list():
    payload = [{"value": key, "label": details["label"], "available": True} for key, details in GAME_ANIMALS.items()]
    return jsonify({"species": payload})


@app.get("/api/gmus")
def gmu_list():
    species_key = normalize_species(request.args.get("species"))
    mapping = get_species_gmu_mapping(species_key)
    gmus = sorted(mapping.keys(), key=lambda x: int(re.match(r"^\d+", x).group(0)) if re.match(r"^\d+", x) else 999)
    return jsonify({"species": species_key, "gmus": gmus})


@app.get("/api/hunts-by-gmu/<gmu>")
def hunts_by_gmu(gmu: str):
    species_key = normalize_species(request.args.get("species"))
    mapping = get_species_gmu_mapping(species_key)

    gmu_key = str(gmu).strip()
    gmu_numeric = re.match(r"^(\d{1,2})", gmu_key)
    normalized = gmu_numeric.group(1) if gmu_numeric else gmu_key
    hunts = mapping.get(normalized, mapping.get(gmu_key, []))
    return jsonify({"species": species_key, "gmu": normalized, "hunt_codes": hunts})


@app.get("/api/hunt/<hunt_code>")
def hunt_details(hunt_code: str):
    species_key = normalize_species(request.args.get("species"))
    code = hunt_code.upper().strip()

    try:
        df = load_dataset(species_key)
    except Exception:
        return jsonify({"species": species_key, "error": f"No draw dataset available for {species_key}."}), 404

    codes = sorted(df["HuntCode"].dropna().unique().tolist())
    if code not in codes:
        return jsonify({"error": f"Unknown hunt code: {code}"}), 404

    lookup = scrape_opportunities_lookup(species_key)
    info = lookup.get(code, {"unit_text": "Not available", "gmus": [], "huntfile_id": "", "details_url": ""})

    details_url = str(info.get("details_url", "") or "")
    gmus = info.get("gmus", []) or []

    links = []
    if details_url:
        links.append({"label": f"ADF&G draw details for {code}", "url": details_url})
    else:
        slug = species_config(species_key)["slug"]
        links.append(
            {
                "label": f"ADF&G draw opportunities for {species_config(species_key)['label']}",
                "url": f"https://www.adfg.alaska.gov/index.cfm?adfg={slug}.opportunities&hunttype=D&performsearch=true",
            }
        )

    for gmu in gmus:
        links.append({"label": f"Open official GMU {gmu} map/info", "url": GMU_INFO_BASE.format(gmu=gmu)})

    map_url = draw_map_url(species_key, code, gmus)
    payload = {
        "species": species_key,
        "hunt_code": code,
        "unit_text": info.get("unit_text", "Not available"),
        "gmus": gmus,
        "resolved_draw_url": map_url,
        "large_hunt_url": map_url,
        "links": links,
        "series": build_series(df, code),
        "draw_odds": build_draw_odds_series(df, code),
    }
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
