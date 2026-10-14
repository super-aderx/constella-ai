-- How many baskets there are. One invoice is one basket.
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

SELECT COUNT(DISTINCT inv_num) AS baskets
FROM scoped
