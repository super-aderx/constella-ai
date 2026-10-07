-- The best-selling product types, by the number of baskets they are in.
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
)

SELECT
  item_tag AS name,
  COUNT(DISTINCT inv_num) AS orders,
  SUM(amount)::FLOAT AS revenue
FROM scoped
WHERE item_tag IS NOT NULL
GROUP BY item_tag
ORDER BY orders DESC, name ASC
LIMIT %(max_items)s
