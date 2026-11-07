-- Every county in the invoices: what a campaign may be limited to.
SELECT DISTINCT county
FROM invoice
WHERE county IS NOT NULL
ORDER BY county ASC
