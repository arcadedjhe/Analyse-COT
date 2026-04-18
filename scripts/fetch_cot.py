"""
Fetch COT TFF data from CFTC and extract NQ E-mini rows.
Saves to data/nq_cot.json (relative to repo root).
Runs via GitHub Actions every Friday evening.
"""
import io, json, zipfile, datetime, os, sys
import requests
import pandas as pd

NQ_CODE = 209742
OUTPUT  = os.path.join(os.path.dirname(__file__), "..", "data", "nq_cot.json")
YEARS   = [datetime.date.today().year - 1, datetime.date.today().year]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GitHub-Actions/2.0; +https://github.com)",
    "Accept": "application/zip,application/octet-stream,*/*",
    "Referer": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
}

COLS = {
    "date": "Report_Date_as_MM_DD_YYYY",
    "oi":   "Open_Interest_All",
    "amL":  "Asset_Mgr_Positions_Long_All",
    "amS":  "Asset_Mgr_Positions_Short_All",
    "lfL":  "Lev_Money_Positions_Long_All",
    "lfS":  "Lev_Money_Positions_Short_All",
    "smL":  "NonRept_Positions_Long_All",
    "smS":  "NonRept_Positions_Short_All",
}

def fetch_year(year):
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_xls_{year}.zip"
    print(f"Fetching {year}: {url}")
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xls_name = next(
            n for n in z.namelist()
            if n.lower().endswith((".xls", ".xlsx")) and not n.startswith("__")
        )
        with z.open(xls_name) as f:
            engine = "xlrd" if xls_name.lower().endswith(".xls") else "openpyxl"
            df = pd.read_excel(f, engine=engine)
    mask = (
        df["CFTC_Contract_Market_Code"].astype(str).str.strip() == str(NQ_CODE)
    ) | (
        df["Market_and_Exchange_Names"].str.upper().str.contains("NASDAQ MINI") &
        ~df["Market_and_Exchange_Names"].str.upper().str.contains("MICRO")
    )
    nq = df[mask].copy()
    print(f"  Found {len(nq)} NQ rows")
    return nq

def process(df):
    rows = []
    for _, r in df.iterrows():
        date_raw = r.get(COLS["date"])
        if pd.isna(date_raw):
            continue
        if isinstance(date_raw, datetime.datetime):
            date = date_raw.date()
        else:
            try:
                date = pd.to_datetime(str(date_raw)).date()
            except Exception:
                continue
        def gi(col):
            v = r.get(col, 0)
            try: return int(v)
            except: return 0
        oi  = gi(COLS["oi"])
        amL = gi(COLS["amL"]); amS = gi(COLS["amS"])
        lfL = gi(COLS["lfL"]); lfS = gi(COLS["lfS"])
        smL = gi(COLS["smL"]); smS = gi(COLS["smS"])
        rows.append({
            "date":    date.isoformat(),
            "dateStr": date.strftime("%d/%m/%y"),
            "oi":  oi,
            "amNet": amL-amS, "amL": amL, "amS": amS,
            "lfNet": lfL-lfS, "lfL": lfL, "lfS": lfS,
            "smNet": smL-smS, "smL": smL, "smS": smS,
        })
    return rows

def load_existing():
    try:
        with open(OUTPUT) as f:
            d = json.load(f)
            return {r["date"]: r for r in d.get("data", [])}
    except Exception:
        return {}

def main():
    existing = load_existing()
    print(f"Existing rows in JSON: {len(existing)}")

    new_rows = []
    for year in YEARS:
        try:
            df = fetch_year(year)
            new_rows.extend(process(df))
        except Exception as e:
            print(f"  Warning: failed for {year}: {e}", file=sys.stderr)

    if not new_rows and not existing:
        print("ERROR: No data available", file=sys.stderr)
        sys.exit(1)

    merged = {**existing}
    for row in new_rows:
        merged[row["date"]] = row

    sorted_rows = sorted(merged.values(), key=lambda r: r["date"])
    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "weeks":   len(sorted_rows),
        "data":    sorted_rows,
    }
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT)), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(sorted_rows)} weeks → {OUTPUT}")
    if sorted_rows:
        print(f"Range: {sorted_rows[0]['date']} → {sorted_rows[-1]['date']}")

if __name__ == "__main__":
    main()
