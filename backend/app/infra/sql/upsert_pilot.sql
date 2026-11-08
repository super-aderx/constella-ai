-- Adds a pilot to an edited draft, or replaces the one it had.
INSERT INTO campaign_pilot (
  campaign_id,
  audience_percent,
  starts_on,
  ends_on,
  discount_percent,
  auto_start
)
VALUES (
  %(campaign_id)s,
  %(audience_percent)s,
  %(starts_on)s,
  %(ends_on)s,
  %(discount_percent)s,
  %(auto_start)s
)
ON CONFLICT (campaign_id) DO UPDATE
  SET
    audience_percent = excluded.audience_percent,
    starts_on = excluded.starts_on,
    ends_on = excluded.ends_on,
    discount_percent = excluded.discount_percent,
    auto_start = excluded.auto_start
RETURNING *
