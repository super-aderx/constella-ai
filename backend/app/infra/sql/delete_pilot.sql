-- Removes the pilot from an edited draft that no longer has one. RETURNING: store._run reads
-- the rows back, and a statement without any has none to read.
DELETE FROM campaign_pilot
WHERE campaign_id = %(campaign_id)s
RETURNING campaign_id
