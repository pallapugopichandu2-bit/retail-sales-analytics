"""Step 2: Build a star schema in SQLite and run the SQL analysis.

Usage: python 02_build_db.py <output folder>
Reads <output folder>/clean_transactions.csv, creates retail.db and
exports each query result in 03_queries.sql to <output folder>/sql_results/.
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

SCHEMA = """
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_country;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_customer (customer_key INTEGER PRIMARY KEY, customer_id INTEGER UNIQUE);
CREATE TABLE dim_product  (product_key INTEGER PRIMARY KEY, stock_code TEXT UNIQUE, description TEXT);
CREATE TABLE dim_country  (country_key INTEGER PRIMARY KEY, country TEXT UNIQUE);
CREATE TABLE dim_date     (date_key INTEGER PRIMARY KEY, full_date TEXT, year INTEGER,
                           quarter INTEGER, month INTEGER, month_name TEXT, year_month TEXT,
                           day_of_week TEXT);
CREATE TABLE fact_sales (
    invoice TEXT, customer_key INTEGER, product_key INTEGER, country_key INTEGER,
    date_key INTEGER, invoice_ts TEXT, quantity INTEGER, unit_price REAL, revenue REAL,
    is_outlier INTEGER,
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY (product_key)  REFERENCES dim_product(product_key),
    FOREIGN KEY (country_key)  REFERENCES dim_country(country_key),
    FOREIGN KEY (date_key)     REFERENCES dim_date(date_key)
);
CREATE INDEX ix_fact_date ON fact_sales(date_key);
CREATE INDEX ix_fact_cust ON fact_sales(customer_key);
CREATE INDEX ix_fact_ctry ON fact_sales(country_key);
"""


def main(out_dir: str) -> None:
    out = Path(out_dir)
    df = pd.read_csv(out / "clean_transactions.csv", parse_dates=["InvoiceDate"])
    db_path = out / "retail.db"
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    cust = pd.DataFrame({"customer_id": df["CustomerID"].unique()})
    cust.insert(0, "customer_key", range(1, len(cust) + 1))
    prod = df.sort_values("InvoiceDate").drop_duplicates("StockCode", keep="last")[["StockCode", "Description"]]
    prod.columns = ["stock_code", "description"]
    prod.insert(0, "product_key", range(1, len(prod) + 1))
    ctry = pd.DataFrame({"country": df["Country"].unique()})
    ctry.insert(0, "country_key", range(1, len(ctry) + 1))

    d = pd.DataFrame({"full_date": df["InvoiceDate"].dt.normalize().unique()}).sort_values("full_date")
    d["date_key"] = d["full_date"].dt.strftime("%Y%m%d").astype(int)
    d["year"] = d["full_date"].dt.year
    d["quarter"] = d["full_date"].dt.quarter
    d["month"] = d["full_date"].dt.month
    d["month_name"] = d["full_date"].dt.strftime("%b")
    d["year_month"] = d["full_date"].dt.strftime("%Y-%m")
    d["day_of_week"] = d["full_date"].dt.strftime("%a")
    d["full_date"] = d["full_date"].dt.strftime("%Y-%m-%d")
    d = d[["date_key", "full_date", "year", "quarter", "month", "month_name", "year_month", "day_of_week"]]

    fact = (
        df.merge(cust, left_on="CustomerID", right_on="customer_id")
        .merge(prod, left_on="StockCode", right_on="stock_code")
        .merge(ctry, left_on="Country", right_on="country")
    )
    fact["date_key"] = fact["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)
    fact = fact.rename(columns={"Invoice": "invoice", "Quantity": "quantity",
                                "UnitPrice": "unit_price", "Revenue": "revenue",
                                "IsOutlier": "is_outlier"})
    fact["invoice_ts"] = fact["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")
    fact = fact[["invoice", "customer_key", "product_key", "country_key", "date_key",
                 "invoice_ts", "quantity", "unit_price", "revenue", "is_outlier"]]

    cust.to_sql("dim_customer", con, if_exists="append", index=False)
    prod.to_sql("dim_product", con, if_exists="append", index=False)
    ctry.to_sql("dim_country", con, if_exists="append", index=False)
    d.to_sql("dim_date", con, if_exists="append", index=False)
    fact.to_sql("fact_sales", con, if_exists="append", index=False)

    res_dir = out / "sql_results"
    res_dir.mkdir(exist_ok=True)
    sql_text = (Path(__file__).parent / "03_queries.sql").read_text()
    for name, query in re.findall(r"--\s*name:\s*(\w+)\s*\n(.*?)(?=\n--\s*name:|\Z)", sql_text, re.S):
        pd.read_sql_query(query.strip().rstrip(";"), con).to_csv(res_dir / f"{name}.csv", index=False)
        print("exported", name)

    # Flat export for Power BI / Tableau
    flat = pd.read_sql_query(
        """SELECT f.invoice, f.invoice_ts, dd.full_date, dd.year, dd.quarter, dd.month, dd.year_month,
                  c.customer_id, co.country, p.stock_code, p.description,
                  f.quantity, f.unit_price, f.revenue
           FROM fact_sales f
           JOIN dim_date dd ON dd.date_key = f.date_key
           JOIN dim_customer c ON c.customer_key = f.customer_key
           JOIN dim_country co ON co.country_key = f.country_key
           JOIN dim_product p ON p.product_key = f.product_key""", con)
    flat.to_csv(out / "powerbi_flat_sales.csv", index=False)
    con.close()
    print(f"\nBuilt {db_path} with {len(fact)} fact rows")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
