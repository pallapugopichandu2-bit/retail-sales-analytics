"""Step 3: RFM segmentation, simple forecast, charts and a findings file.

Usage: python 04_analysis.py <output folder>
Reads <output folder>/clean_transactions.csv and sql_results/*.csv.
Writes rfm_customers.csv, rfm_segments.csv, forecast_comparison.csv,
charts/*.png and findings.md.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLUE, GREY, ORANGE = "#2a6f97", "#8d99ae", "#d1495b"


def style(ax, title, xlabel="", ylabel=""):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def rfm(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["InvoiceDate"].max() + pd.Timedelta(days=1)
    g = df.groupby("CustomerID").agg(
        recency=("InvoiceDate", lambda s: (snapshot - s.max()).days),
        frequency=("Invoice", "nunique"),
        monetary=("Revenue", "sum"),
    )
    g["R"] = pd.qcut(g["recency"].rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
    g["F"] = pd.qcut(g["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    g["M"] = pd.qcut(g["monetary"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)

    def segment(r):
        if r.R >= 3 and r.F >= 3 and r.M >= 3:
            return "Champions"
        if r.R >= 3 and r.F >= 2:
            return "Loyal"
        if r.R == 4 and r.F == 1:
            return "New customers"
        if r.R <= 2 and r.F >= 3 and r.M >= 3:
            return "At risk (high value)"
        if r.R <= 2:
            return "Lost / inactive"
        return "Needs attention"

    g["segment"] = g.apply(segment, axis=1)
    return g.reset_index()


def forecast(monthly: pd.Series, holdout: int = 3):
    """Compare a 3-month moving average with a seasonal-naive forecast on a holdout."""
    train, test = monthly.iloc[:-holdout], monthly.iloc[-holdout:]
    ma = pd.Series([train.iloc[-3:].mean()] * holdout, index=test.index)
    if len(train) >= 12:
        # same months one year earlier
        sn = pd.Series([monthly.iloc[-holdout - 12 + i] for i in range(holdout)], index=test.index)
    else:
        sn = ma.copy()
    comp = pd.DataFrame({"actual": test, "moving_avg_3m": ma, "seasonal_naive": sn})
    mae = {"moving_avg_3m": float((comp["actual"] - comp["moving_avg_3m"]).abs().mean()),
           "seasonal_naive": float((comp["actual"] - comp["seasonal_naive"]).abs().mean())}
    # Next 3 months using the better method
    best = min(mae, key=mae.get)
    idx = pd.period_range(monthly.index[-1], periods=4, freq="M")[1:]
    if best == "seasonal_naive" and len(monthly) >= 12:
        nxt = [monthly.iloc[-12 + i] for i in range(3)]
    else:
        nxt = [monthly.iloc[-3:].mean()] * 3
    future = pd.Series(nxt, index=idx.astype(str))
    return comp, mae, best, future


def main(out_dir: str) -> None:
    out = Path(out_dir)
    charts = out / "charts"
    charts.mkdir(exist_ok=True)
    df = pd.read_csv(out / "clean_transactions.csv", parse_dates=["InvoiceDate"])
    sql = out / "sql_results"

    # ---------- RFM ----------
    r = rfm(df)
    r.to_csv(out / "rfm_customers.csv", index=False)
    seg = (r.groupby("segment")
             .agg(customers=("CustomerID", "count"), revenue=("monetary", "sum"),
                  avg_recency_days=("recency", "mean"), avg_orders=("frequency", "mean"))
             .sort_values("revenue", ascending=False).round(1))
    seg["pct_of_revenue"] = (100 * seg["revenue"] / seg["revenue"].sum()).round(1)
    seg.to_csv(out / "rfm_segments.csv")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(seg.index[::-1], seg["pct_of_revenue"][::-1], color=BLUE)
    for i, v in enumerate(seg["pct_of_revenue"][::-1]):
        ax.text(v + 0.5, i, f"{v}%", va="center", fontsize=9)
    style(ax, "Share of revenue by customer segment (RFM)", "% of total revenue")
    fig.tight_layout(); fig.savefig(charts / "rfm_segments.png", dpi=160); plt.close(fig)

    # ---------- Monthly trend and forecast ----------
    df["ym"] = df["InvoiceDate"].dt.to_period("M")
    monthly = df.groupby("ym")["Revenue"].sum()
    monthly = monthly.iloc[:-1] if df["InvoiceDate"].max().day < 28 else monthly  # drop partial last month
    comp, mae, best, future = forecast(monthly)
    comp.to_csv(out / "forecast_comparison.csv")
    future.rename("forecast_revenue").to_csv(out / "forecast_next_3_months.csv")

    fig, ax = plt.subplots(figsize=(9, 4))
    labels = list(monthly.index.astype(str)) + list(future.index)
    n_act = len(monthly)
    ax.plot(range(n_act), monthly.values, color=BLUE, lw=2, label="Actual")
    ax.plot(range(n_act - 1, len(labels)), [monthly.values[-1]] + list(future.values),
            color=ORANGE, lw=2, ls="--", marker="o", label=f"Forecast ({best})")
    ticks = list(range(0, len(labels), 3))
    ax.set_xticks(ticks)
    ax.set_xticklabels([labels[i] for i in ticks], rotation=45, ha="right", fontsize=8)
    ax.legend(frameon=False)
    style(ax, "Monthly revenue and 3-month forecast", ylabel="Revenue")
    fig.tight_layout(); fig.savefig(charts / "monthly_revenue_forecast.png", dpi=160); plt.close(fig)

    # ---------- Country chart (excluding UK) ----------
    cx = pd.read_csv(sql / "revenue_by_country_excl_uk.csv").head(10)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(cx["country"][::-1], cx["revenue"][::-1], color=BLUE)
    style(ax, "Top 10 countries by revenue (excluding UK)", "Revenue")
    fig.tight_layout(); fig.savefig(charts / "top_countries_excl_uk.png", dpi=160); plt.close(fig)

    # ---------- Seasonality ----------
    s = pd.read_csv(sql / "seasonality_by_month.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    peak = s["avg_revenue"].idxmax()
    ax.bar(s["month_name"], s["avg_revenue"], color=[ORANGE if i == peak else GREY for i in s.index])
    style(ax, "Average revenue by calendar month", ylabel="Average revenue")
    fig.tight_layout(); fig.savefig(charts / "seasonality.png", dpi=160); plt.close(fig)

    # ---------- Findings file (numbers come straight from the data) ----------
    k = pd.read_csv(sql / "kpi_summary.csv").iloc[0]
    c = pd.read_csv(sql / "revenue_by_country.csv")
    rep = pd.read_csv(sql / "repeat_customer_rate.csv").iloc[0]
    conc = pd.read_csv(sql / "customer_concentration.csv")
    top_prod = pd.read_csv(sql / "top_products.csv").iloc[0]
    top_seg = seg.index[0]
    lines = [
        "# Key findings (generated from the data)",
        "",
        f"- Total revenue {k.total_revenue:,.0f} from {int(k.total_orders):,} orders and {int(k.total_customers):,} customers; average order value {k.avg_order_value:,.2f}.",
        f"- Top country: {c.iloc[0].country} with {c.iloc[0].pct_of_total}% of revenue. Outside the top country, {cx.iloc[0].country} leads with {cx.iloc[0].revenue:,.0f}.",
        f"- Repeat customer rate: {rep.repeat_rate_pct}% ({int(rep.repeat_customers):,} of {int(rep.all_customers):,}).",
        f"- Top 10% of customers bring {conc.iloc[0].pct_of_revenue}% of revenue.",
        f"- Best-selling product by revenue: {top_prod.description} ({top_prod.revenue:,.0f}).",
        f"- Peak month on average: {s.loc[peak, 'month_name']}.",
        f"- Biggest RFM segment by revenue: {top_seg} ({seg.iloc[0].pct_of_revenue}% of revenue).",
        f"- Forecast test (last 3 months held out): MAE moving average {mae['moving_avg_3m']:,.0f} vs seasonal naive {mae['seasonal_naive']:,.0f}; best method: {best}.",
    ]
    (out / "findings.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
