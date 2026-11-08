-- Replaces what the wizard edits on a draft. The client_token and the source proposal stay as
-- they were saved.
UPDATE campaign SET
  title = %(title)s,
  strategy = %(strategy)s,
  slogan = %(slogan)s,
  item_types = %(item_types)s::TEXT[],
  products = %(products)s::TEXT[],
  discount_percent = %(discount_percent)s,
  starts_on = %(starts_on)s,
  ends_on = %(ends_on)s,
  segment = %(segment)s,
  counties = %(counties)s::TEXT[]
WHERE id = %(id)s
RETURNING *
