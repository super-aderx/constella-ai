-- The best-selling products inside each of the given product types.
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

products AS (
  SELECT
    item_tag AS tag,
    item_name AS name,
    COUNT(DISTINCT inv_num) AS orders,
    SUM(amount)::FLOAT AS revenue,
    ROW_NUMBER() OVER (
      PARTITION BY item_tag
      ORDER BY COUNT(DISTINCT inv_num) DESC, item_name ASC
    ) AS position
  FROM scoped
  WHERE item_tag = ANY(%(names)s)
  GROUP BY item_tag, item_name
)

SELECT
  tag,
  name,
  orders,
  revenue
FROM products
WHERE position <= %(max_products)s
ORDER BY tag ASC, position ASC
