-- The campaigns the store team saves, and their optional pilots. Every statement creates only
-- what is missing, so this file is safe to run again (make migrate).

CREATE TABLE IF NOT EXISTS campaign (
  id UUID PRIMARY KEY, -- made in Python (uuid4): no extension needed
  -- The AI proposal it came from, as shown (name, basis, items, discount_percent, audience,
  -- reason). NULL = not from one.
  source_proposal JSONB,
  client_token UUID NOT NULL UNIQUE, -- one per wizard opening: a double click saves once
  status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled')),
  title TEXT NOT NULL CHECK (title <> ''),
  strategy TEXT NOT NULL CHECK (strategy <> ''),
  item_types TEXT[] NOT NULL DEFAULT '{}', -- invoice.item_tag values
  products TEXT[] NOT NULL DEFAULT '{}', -- invoice.item_name values
  discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
  starts_on DATE NOT NULL,
  ends_on DATE NOT NULL,
  segment TEXT, -- NULL = all customers
  counties TEXT[] NOT NULL DEFAULT '{}', -- empty = all counties
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (ends_on >= starts_on),
  CHECK (CARDINALITY(item_types) + CARDINALITY(products) > 0)
);

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
