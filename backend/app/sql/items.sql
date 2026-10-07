-- The leading product types: the best sellers by the number of baskets they are in, and the
-- revenue leaders, which that ranking alone can leave out.
-- `scoped` is the invoice lines inside the chosen period and customer segment (null: no filter).
WITH scoped AS (
  SELECT
    inv_num,
    item_tag,
    item_name,
    amount
  FROM invoice
  WHERE
    (%(segment)s::TEXT IS NULL OR segment = %(segment)s)
    AND (
      %(days)s::INT IS NULL
      OR datetime >= (
        SELECT MAX(latest.datetime) FROM invoice AS latest
      ) - MAKE_INTERVAL(days => %(days)s)
    )
),

ranked AS (
  SELECT
    item_tag AS name,
    COUNT(DISTINCT inv_num) AS orders,
    SUM(amount)::FLOAT AS revenue,
    ROW_NUMBER() OVER (ORDER BY COUNT(DISTINCT inv_num) DESC, item_tag ASC) AS by_orders,
    ROW_NUMBER() OVER (ORDER BY SUM(amount) DESC, item_tag ASC) AS by_revenue
  FROM scoped
  WHERE item_tag IS NOT NULL
  GROUP BY item_tag
)

SELECT
  name,
  orders,
  revenue
FROM ranked
WHERE by_orders <= %(max_items)s OR by_revenue <= %(max_revenue_items)s
ORDER BY orders DESC, name ASC
