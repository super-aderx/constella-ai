-- Every campaign and its pilot, newest first: the Campaigns tab. The pilot's columns are NULL when
-- it has none.
SELECT
  c.id,
  c.client_token,
  c.source_proposal,
  c.status,
  c.title,
  c.strategy,
  c.slogan,
  c.item_types,
  c.products,
  c.discount_percent,
  c.starts_on,
  c.ends_on,
  c.segment,
  c.counties,
  c.created_at,
  c.launched_at,
  c.approved_at,
  c.ended_at,
  c.cancelled_at,
  p.campaign_id AS pilot_campaign_id,
  p.audience_percent AS pilot_audience_percent,
  p.starts_on AS pilot_starts_on,
  p.ends_on AS pilot_ends_on,
  p.discount_percent AS pilot_discount_percent,
  p.auto_start AS pilot_auto_start
FROM campaign AS c
LEFT JOIN campaign_pilot AS p ON c.id = p.campaign_id
ORDER BY c.created_at DESC, c.id
