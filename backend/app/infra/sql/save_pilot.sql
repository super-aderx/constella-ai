-- Stores a campaign's pilot, in the same transaction as the campaign.
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
RETURNING *
