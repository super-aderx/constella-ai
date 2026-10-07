-- Every customer segment, for the filter.
SELECT DISTINCT segment
FROM invoice
WHERE segment IS NOT NULL
ORDER BY segment ASC
