"""Step 1: Clean the Online Retail II data.

Usage: python 01_clean.py <input .xlsx or .csv> <output folder>

Expected columns (UCI Online Retail II): Invoice, StockCode, Description,
Quantity, InvoiceDate, Price, Customer ID, Country.
If the xlsx has two sheets (2009-2010, 2010-2011) both are read and combined.
"""
import sys
from pathlib import Path

import pandas as pd


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None)
        return pd.concat(sheets.values(), ignore_index=True)
    return pd.read_csv(path, encoding="latin-1")


def main(src: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = load(Path(src))
    df = df.rename(columns={"Customer ID": "CustomerID", "Price": "UnitPrice"})
    log = [("raw rows", len(df))]

    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df = df.dropna(subset=["InvoiceDate"])
    log.append(("valid invoice date", len(df)))

    df["Invoice"] = df["Invoice"].astype(str)
    cancelled = df["Invoice"].str.startswith("C")
    df = df[~cancelled]
    log.append(("after removing cancellations (invoice starts with C)", len(df)))

    df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
    log.append(("after removing quantity <= 0 or price <= 0", len(df)))

    df = df.dropna(subset=["CustomerID"])
    df["CustomerID"] = df["CustomerID"].astype(float).astype(int)
    log.append(("after removing missing customer ID", len(df)))

    # Non-product codes (postage, bank charges, samples, etc.)
    non_product = r"^(POST|DOT|M|BANK CHARGES|AMAZONFEE|S|D|CRUK|ADJUST.*|TEST.*)$"
    df = df[~df["StockCode"].astype(str).str.upper().str.match(non_product)]
    log.append(("after removing non-product stock codes", len(df)))

    before = len(df)
    df = df.drop_duplicates()
    log.append((f"after removing exact duplicates ({before - len(df)} removed)", len(df)))

    df["Description"] = df["Description"].fillna("UNKNOWN").str.strip().str.upper()
    df["Country"] = df["Country"].str.strip()
    df["Revenue"] = (df["Quantity"] * df["UnitPrice"]).round(2)

    # Cap extreme outliers at the 99.9th percentile of line revenue (kept in a flag)
    cap = df["Revenue"].quantile(0.999)
    df["IsOutlier"] = (df["Revenue"] > cap).astype(int)
    log.append((f"flagged outlier lines above {cap:.2f} (kept, flagged)", int(df["IsOutlier"].sum())))

    df.to_csv(out / "clean_transactions.csv", index=False)
    pd.DataFrame(log, columns=["step", "rows"]).to_csv(out / "cleaning_log.csv", index=False)
    print(pd.DataFrame(log, columns=["step", "rows"]).to_string(index=False))
    print(f"\nSaved {len(df)} clean rows to {out / 'clean_transactions.csv'}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
