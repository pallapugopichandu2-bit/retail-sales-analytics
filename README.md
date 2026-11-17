# European Retail Sales Analytics and Business Intelligence Dashboard

Analysis of two years of online retail orders from customers across Europe, using Python, SQL (star schema) and Power BI.

## Business questions
1. Which countries and products drive revenue?
2. When are sales strongest (month, day of week)?
3. Who are the most valuable customers, and which good customers are at risk of leaving?
4. What will revenue look like in the next 3 months?

## Data
UCI Online Retail II (download from the UCI Machine Learning Repository or Kaggle). Place the file anywhere and pass its path to step 1.

## How to run
```
pip install pandas numpy matplotlib openpyxl
python 01_clean.py  online_retail_II.xlsx  output
python 02_build_db.py  output
python 04_analysis.py  output
```
(`03_queries.sql` is read by step 2.)

## What each step does
| Step | File | Output |
|---|---|---|
| 1 | `01_clean.py` | `clean_transactions.csv`, `cleaning_log.csv` (rows kept after every cleaning rule) |
| 2 | `02_build_db.py` + `03_queries.sql` | `retail.db` (star schema: fact_sales + 4 dimensions), `sql_results/*.csv`, `powerbi_flat_sales.csv` |
| 3 | `04_analysis.py` | RFM segments, forecast comparison, `charts/*.png`, `findings.md` |

## Cleaning rules
Removed cancelled invoices, rows with quantity or price of zero or below, rows with no customer ID, non-product codes (postage, bank charges, samples) and exact duplicates. Very large order lines (top 0.1%) are flagged, not removed.

## Method
- **Star schema:** one fact table of order lines plus customer, product, country and date dimensions.
- **RFM:** each customer scored 1-4 on recency, frequency and monetary value, then grouped into segments (Champions, Loyal, New, At risk, Lost).
- **Forecast:** a 3-month moving average and a seasonal-naive forecast (same month last year) are tested on the last 3 months; the one with the lower error is used for the next 3 months.

## Power BI dashboard (build from `powerbi_flat_sales.csv` and `rfm_customers.csv`)
- Page 1 Executive summary: revenue, orders, customers, average order value, monthly trend
- Page 2 Countries and products: country map, top 10 countries excluding UK, top products
- Page 3 Customers: RFM segments, revenue by segment, customer concentration
- Page 4 Forecast: actual vs forecast, seasonality by month

## Results
See `findings.md` after running the pipeline on the real data. Copy the numbers into this section and add your recommendations (which country to grow, which products to stock before peak season, which at-risk customers to target).

## Tools
Python (Pandas, NumPy, Matplotlib), SQL (SQLite), Power BI
