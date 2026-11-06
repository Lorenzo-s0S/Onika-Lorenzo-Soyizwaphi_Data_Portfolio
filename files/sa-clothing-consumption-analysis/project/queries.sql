-- Q1. Annual averages: clothing inflation vs real consumption growth
SELECT EXTRACT(YEAR FROM date)::int AS year,
       ROUND(AVG(cpi_yoy)::numeric, 2)  AS avg_clothing_inflation,
       ROUND(AVG(rfce_yoy)::numeric, 2) AS avg_real_consumption_growth
FROM clothing_consumption
WHERE cpi_yoy IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- Q2. Window function: rolling 4-quarter average of clothing inflation
SELECT date, cpi_yoy,
       ROUND(AVG(cpi_yoy) OVER (ORDER BY date ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)::numeric, 2) AS clothing_inflation_4q_avg,
       rfce_yoy
FROM clothing_consumption
WHERE cpi_yoy IS NOT NULL
ORDER BY date;

-- Q3. Ranking: five weakest consumption quarters outside the COVID-19 window
SELECT date, rfce_yoy, cpi_yoy, RANK() OVER (ORDER BY rfce_yoy) AS weakness_rank
FROM clothing_consumption
WHERE NOT covid AND rfce_yoy IS NOT NULL
ORDER BY weakness_rank
LIMIT 5;

-- Q4. CTE: consumption growth in above- vs below-average clothing-inflation regimes (ex-COVID)
WITH stats AS (
    SELECT AVG(cpi_yoy) AS mean_infl FROM clothing_consumption WHERE NOT covid AND cpi_yoy IS NOT NULL
)
SELECT CASE WHEN c.cpi_yoy > s.mean_infl THEN 'above-average clothing inflation' ELSE 'below-average clothing inflation' END AS regime,
       COUNT(*) AS quarters,
       ROUND(AVG(c.rfce_yoy)::numeric, 2) AS avg_real_consumption_growth
FROM clothing_consumption c CROSS JOIN stats s
WHERE NOT c.covid AND c.cpi_yoy IS NOT NULL AND c.rfce_yoy IS NOT NULL
GROUP BY 1
ORDER BY 1;
