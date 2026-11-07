-- A stored campaign and its pilot, by the client_token it was saved with: what a repeated save
-- returns. The pilot's columns are NULL when it has none.
SELECT
  c.id,
  c.client_token,
  c.source_proposal,
  c.status,
  c.title,
  c.strategy,
  c.item_types,
  c.products,
  c.discount_percent,
  c.starts_on,
  c.ends_on,
  c.segment,
  c.counties,
  c.created_at,
  p.campaign_id AS pilot_campaign_id,
  p.audience_percent AS pilot_audience_percent,
  p.starts_on AS pilot_starts_on,
  p.ends_on AS pilot_ends_on,
  p.discount_percent AS pilot_discount_percent,
  p.auto_start AS pilot_auto_start
FROM campaign AS c
LEFT JOIN campaign_pilot AS p ON c.id = p.campaign_id
WHERE c.client_token = %(client_token)s
