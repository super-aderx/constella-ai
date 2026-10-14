-- Every product and the product type it belongs to, over all the data: what a loose name or a
-- product's name is looked up in.
SELECT DISTINCT
  item_tag AS tag,
  item_name AS name
FROM invoice
WHERE item_tag IS NOT NULL AND item_name IS NOT NULL
ORDER BY tag ASC, name ASC
