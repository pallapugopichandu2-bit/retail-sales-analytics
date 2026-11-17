-- name: kpi_summary
SELECT ROUND(SUM(revenue), 2)                         AS total_revenue,
       COUNT(DISTINCT invoice)                        AS total_orders,
       COUNT(DISTINCT customer_key)                   AS total_customers,
       ROUND(SUM(revenue) / COUNT(DISTINCT invoice), 2) AS avg_order_value
FROM fact_sales;

-- name: revenue_by_country
SELECT co.country,
       ROUND(SUM(f.revenue), 2)             AS revenue,
       COUNT(DISTINCT f.invoice)            AS orders,
       COUNT(DISTINCT f.customer_key)       AS customers,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.invoice), 2) AS avg_order_value,
       ROUND(100.0 * SUM(f.revenue) / (SELECT SUM(revenue) FROM fact_sales), 2) AS pct_of_total
FROM fact_sales f JOIN dim_country co ON co.country_key = f.country_key
GROUP BY co.country
ORDER BY revenue DESC;

-- name: revenue_by_country_excl_uk
SELECT co.country,
       ROUND(SUM(f.revenue), 2)       AS revenue,
       COUNT(DISTINCT f.invoice)      AS orders,
       COUNT(DISTINCT f.customer_key) AS customers
FROM fact_sales f JOIN dim_country co ON co.country_key = f.country_key
WHERE co.country <> 'United Kingdom'
GROUP BY co.country
ORDER BY revenue DESC;

-- name: monthly_revenue_growth
WITH m AS (
    SELECT dd.year_month, ROUND(SUM(f.revenue), 2) AS revenue,
           COUNT(DISTINCT f.invoice) AS orders
    FROM fact_sales f JOIN dim_date dd ON dd.date_key = f.date_key
    GROUP BY dd.year_month
)
SELECT year_month, revenue, orders,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY year_month))
             / LAG(revenue) OVER (ORDER BY year_month), 2) AS mom_growth_pct
FROM m
ORDER BY year_month;

-- name: top_products
SELECT p.stock_code, p.description,
       SUM(f.quantity)            AS units_sold,
       ROUND(SUM(f.revenue), 2)   AS revenue
FROM fact_sales f JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.stock_code, p.description
ORDER BY revenue DESC
LIMIT 20;

-- name: day_of_week_pattern
SELECT dd.day_of_week,
       ROUND(SUM(f.revenue), 2)  AS revenue,
       COUNT(DISTINCT f.invoice) AS orders
FROM fact_sales f JOIN dim_date dd ON dd.date_key = f.date_key
GROUP BY dd.day_of_week
ORDER BY revenue DESC;

-- name: seasonality_by_month
SELECT dd.month, dd.month_name,
       ROUND(AVG(monthly.revenue), 2) AS avg_revenue
FROM (
    SELECT dd2.year, dd2.month, SUM(f.revenue) AS revenue
    FROM fact_sales f JOIN dim_date dd2 ON dd2.date_key = f.date_key
    GROUP BY dd2.year, dd2.month
) monthly
JOIN (SELECT DISTINCT month, month_name FROM dim_date) dd ON dd.month = monthly.month
GROUP BY dd.month, dd.month_name
ORDER BY dd.month;

-- name: repeat_customer_rate
WITH orders_per_customer AS (
    SELECT customer_key, COUNT(DISTINCT invoice) AS orders
    FROM fact_sales GROUP BY customer_key
)
SELECT SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
       COUNT(*)                                       AS all_customers,
       ROUND(100.0 * SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
FROM orders_per_customer;

-- name: customer_concentration
WITH cust AS (
    SELECT customer_key, SUM(revenue) AS revenue FROM fact_sales GROUP BY customer_key
), ranked AS (
    SELECT revenue, NTILE(10) OVER (ORDER BY revenue DESC) AS decile FROM cust
)
SELECT decile,
       COUNT(*)                 AS customers,
       ROUND(SUM(revenue), 2)   AS revenue,
       ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM cust), 2) AS pct_of_revenue
FROM ranked GROUP BY decile ORDER BY decile;
