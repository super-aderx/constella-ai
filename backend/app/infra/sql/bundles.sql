-- Sets of three among the given product types and the baskets that hold all three.
-- a < b < c, so each set appears once.
-- `scoped` is the invoice lines inside the chosen period and customer segment (null: no filter).
WITH scoped AS (
  SELECT
    inv_num,
    item_tag
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
  z.item_tag AS c,
  COUNT(*) AS co_orders
FROM lines AS x
INNER JOIN lines AS y
  ON x.inv_num = y.inv_num AND x.item_tag < y.item_tag
INNER JOIN lines AS z
  ON y.inv_num = z.inv_num AND y.item_tag < z.item_tag
GROUP BY x.item_tag, y.item_tag, z.item_tag
HAVING COUNT(*) >= %(min_co_orders)s
