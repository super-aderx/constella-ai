-- Pairs among the given product types and the baskets that hold both.
-- a < b, so each pair appears once.
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

lines AS (
  SELECT DISTINCT
    inv_num,
    item_tag
  FROM scoped
  WHERE item_tag = ANY(%(names)s)
)

SELECT
  x.item_tag AS a,
  y.item_tag AS b,
  COUNT(*) AS co_orders
FROM lines AS x
INNER JOIN lines AS y
  ON x.inv_num = y.inv_num AND x.item_tag < y.item_tag
GROUP BY x.item_tag, y.item_tag
HAVING COUNT(*) >= %(min_co_orders)s
