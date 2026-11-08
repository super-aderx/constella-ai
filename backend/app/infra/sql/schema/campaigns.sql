-- The campaigns the store team saves, and their optional pilots. Every statement creates only
-- what is missing, so this file is safe to run again (make migrate).

CREATE TABLE IF NOT EXISTS campaign (
  id UUID PRIMARY KEY, -- made in Python (uuid4): no extension needed
  -- The AI proposal it came from, as shown (name, basis, items, discount_percent, audience,
  -- reason). NULL = not from one.
  source_proposal JSONB,
  client_token UUID NOT NULL UNIQUE, -- one per wizard opening: a double click saves once
  -- Only facts that don't move with the date: the status a campaign shows is worked out from
  -- these, its dates and today (app/campaigns.py, status_of).
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'launched')),
  title TEXT NOT NULL CHECK (title <> ''),
  strategy TEXT NOT NULL CHECK (strategy <> ''),
  slogan TEXT CHECK (CHAR_LENGTH(slogan) <= 100), -- NULL = no slogan
  item_types TEXT[] NOT NULL DEFAULT '{}', -- invoice.item_tag values
  products TEXT[] NOT NULL DEFAULT '{}', -- invoice.item_name values
  discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
  starts_on DATE NOT NULL,
  ends_on DATE NOT NULL,
  segment TEXT, -- NULL = all customers
  counties TEXT[] NOT NULL DEFAULT '{}', -- empty = all counties
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  launched_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ, -- a pilot on hold was approved
  ended_at TIMESTAMPTZ, -- "End now"
  cancelled_at TIMESTAMPTZ,
  CHECK (ends_on >= starts_on),
  CHECK (CARDINALITY(item_types) + CARDINALITY(products) > 0)
);

-- Campaigns saved before the lifecycle (CAI-7) were created with only 'scheduled'. Every step
-- below either adds only what is missing or rewrites rows that no longer exist on a second run,
-- so the file stays safe to run again.
ALTER TABLE campaign ADD COLUMN IF NOT EXISTS slogan TEXT CHECK (CHAR_LENGTH(slogan) <= 100);
ALTER TABLE campaign ADD COLUMN IF NOT EXISTS launched_at TIMESTAMPTZ;
ALTER TABLE campaign ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
ALTER TABLE campaign ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
ALTER TABLE campaign ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
-- A 'scheduled' campaign was already as good as launched: it counts as launched when it was
-- saved. The old check would refuse 'launched', so it is dropped first and put back after.
ALTER TABLE campaign DROP CONSTRAINT IF EXISTS campaign_status_check;
UPDATE campaign SET
  status = 'launched',
  launched_at = COALESCE(launched_at, created_at)
WHERE status = 'scheduled';
ALTER TABLE campaign ADD CONSTRAINT campaign_status_check CHECK (status IN ('draft', 'launched'));
ALTER TABLE campaign ALTER COLUMN status SET DEFAULT 'draft';

-- No row: the campaign has no pilot. "The pilot ends before the campaign starts" spans the two
-- tables, so the API checks it (app/campaigns.py), not a constraint.
CREATE TABLE IF NOT EXISTS campaign_pilot (
  campaign_id UUID PRIMARY KEY REFERENCES campaign (id) ON DELETE CASCADE,
  audience_percent INTEGER NOT NULL CHECK (audience_percent BETWEEN 1 AND 99),
  starts_on DATE NOT NULL,
  ends_on DATE NOT NULL,
  discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
  auto_start BOOLEAN NOT NULL, -- true: start the campaign when the pilot passes
  CHECK (ends_on >= starts_on)
);
