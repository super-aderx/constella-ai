-- One campaign and its pilot, locked until the transaction ends, so two people acting on it at
-- once take turns: the second sees what the first did. Only the campaign row is locked: Postgres
-- can't lock the nullable side of an outer join, and every change to a pilot goes through its
-- campaign first.
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
WHERE c.id = %(id)s
FOR UPDATE OF c
