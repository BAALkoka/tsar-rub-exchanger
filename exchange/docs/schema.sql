-- SQL schema (Postgres) minimal

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  external_id TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  network TEXT,
  amount_tokens NUMERIC,
  status TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE deposits (
  id SERIAL PRIMARY KEY,
  tx_hash TEXT,
  network TEXT,
  to_address TEXT,
  amount_tokens NUMERIC,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE payouts (
  id SERIAL PRIMARY KEY,
  order_id INTEGER,
  amount_rub NUMERIC,
  provider TEXT,
  provider_id TEXT,
  status TEXT,
  created_at TIMESTAMP DEFAULT now()
);
