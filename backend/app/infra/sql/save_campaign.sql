-- Stores a campaign once per client_token. A repeated token inserts nothing and returns no row,
-- and the caller reads the stored one instead.
INSERT INTO campaign (
  id,
  client_token,
  source_proposal,
  title,
  strategy,
  item_types,
  products,
  discount_percent,
  starts_on,
  ends_on,
  segment,
  counties
)
VALUES (
  %(id)s,
  %(client_token)s,
  %(source_proposal)s,
  %(title)s,
  %(strategy)s,
  %(item_types)s::TEXT[],
  %(products)s::TEXT[],
  %(discount_percent)s,
  %(starts_on)s,
  %(ends_on)s,
  %(segment)s,
  %(counties)s::TEXT[]
)
ON CONFLICT (client_token) DO NOTHING
RETURNING *
