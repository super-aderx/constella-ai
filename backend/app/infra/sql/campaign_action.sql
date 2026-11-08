-- Records an action as the fact it leaves behind. Launch is the only one that changes the stored
-- status; the others only stamp when they happened, and status_of reads the stamps.
UPDATE campaign SET
  status = CASE WHEN %(action)s::TEXT = 'launch' THEN 'launched' ELSE status END,
  launched_at = CASE WHEN %(action)s::TEXT = 'launch' THEN NOW() ELSE launched_at END,
  approved_at = CASE WHEN %(action)s::TEXT = 'approve' THEN NOW() ELSE approved_at END,
  ended_at = CASE WHEN %(action)s::TEXT = 'end' THEN NOW() ELSE ended_at END,
  cancelled_at = CASE WHEN %(action)s::TEXT = 'cancel' THEN NOW() ELSE cancelled_at END
WHERE id = %(id)s
RETURNING *
