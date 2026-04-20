"""
Fetch NQ=F daily price data via yfinance and compute EMA 18 / EMA 40.
Saves to data/nq_price.json (relative to repo root).
"""
import json, datetime, os, sys
import yfinance as yf
import pandas as pd

OUTPUT  = os.path.join(os.path.dirname(__file__), "..", "data", "nq_price.json")
TICKER  = "NQ=F"
PERIOD  = "2y"   # 2 years of daily data

def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def main():
    print(f"Fetching {TICKER} daily data ({PERIOD})...")
    df = yf.download(TICKER, period=PERIOD, interval="1d", auto_adjust=True, progress=False)

    if df.empty:
        print("ERROR: No price data returned", file=sys.stderr)
        sys.exit(1)

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close"])
    df["ema18"] = compute_ema(df["Close"], 18)
    df["ema40"] = compute_ema(df["Close"], 40)

    rows = []
    for date, row in df.iterrows():
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)[:10]
        rows.append({
            "date":    date_str,
            "close":   round(float(row["Close"]), 2),
            "ema18":   round(float(row["ema18"]), 2),
            "ema40":   round(float(row["ema40"]), 2),
        })

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ticker":  TICKER,
        "days":    len(rows),
        "data":    rows,
    }

    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT)), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(rows)} days → {OUTPUT}")
    print(f"Range: {rows[0]['date']} → {rows[-1]['date']}")

if __name__ == "__main__":
    main()
