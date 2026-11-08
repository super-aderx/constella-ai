-- Deletes a draft. Its pilot goes with it (ON DELETE CASCADE). RETURNING: store._run reads the
-- rows back, and a statement without any has none to read.
DELETE FROM campaign
WHERE id = %(id)s
RETURNING id
