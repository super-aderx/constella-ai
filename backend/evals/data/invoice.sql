-- The sample invoice table for the evals, in the test database (TEST_DATABASE_URL).
-- One row per invoice line; the columns match evals/data/invoice.csv.
--
-- Create the database once, connected to any other database on the server:
--   CREATE DATABASE constella_test;
-- Then run this file in it.
DROP TABLE IF EXISTS invoice;

CREATE TABLE invoice (
  inv_num TEXT NOT NULL,
  datetime TIMESTAMP NOT NULL,
  user_id TEXT NOT NULL,
  segment TEXT NOT NULL,
  county TEXT NOT NULL,
  city TEXT NOT NULL,
  item_tag TEXT NOT NULL,
  item_name TEXT NOT NULL,
  item_brand_name TEXT NOT NULL,
  price NUMERIC(12, 2) NOT NULL,
  unit INTEGER NOT NULL,
  amount NUMERIC(12, 2) NOT NULL
);

CREATE INDEX invoice_inv_num ON invoice (inv_num);
