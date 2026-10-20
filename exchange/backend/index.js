// backend/index.js — minimal API scaffold

require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const { Pool } = require('pg');

const app = express();
app.use(bodyParser.json());

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

app.get('/health', (req, res) => res.json({ ok: true }));

// Create new order (user indicates network, tx hash or will deposit to address)
app.post('/api/orders', async (req, res) => {
  const { userId, network, amountTokens, depositTx } = req.body;
  // validate
  if (!userId || !network || !amountTokens) return res.status(400).json({ error: 'missing' });
  const client = await pool.connect();
  try {
    const result = await client.query(
      `INSERT INTO orders (user_id, network, amount_tokens, status, created_at) VALUES ($1,$2,$3,$4,now()) RETURNING *`,
      [userId, network, amountTokens, 'pending']
    );
    res.json({ order: result.rows[0] });
  } finally { client.release(); }
});

// Admin: list pending orders
app.get('/api/admin/orders', async (req, res) => {
  const client = await pool.connect();
  try {
    const { rows } = await client.query(`SELECT * FROM orders ORDER BY created_at DESC LIMIT 200`);
    res.json({ orders: rows });
  } finally { client.release(); }
});

// Webhook hit by chain watchers when deposit confirmed
app.post('/api/webhook/deposit', async (req, res) => {
  const { txHash, network, toAddress, amountTokens, userId } = req.body;
  // find order or create deposit record
  // For MVP we'll store deposit and mark order
  const client = await pool.connect();
  try {
    await client.query(`INSERT INTO deposits (tx_hash, network, to_address, amount_tokens, created_at) VALUES ($1,$2,$3,$4,now())`,
      [txHash, network, toAddress, amountTokens]);
    // TODO: match order -> mark paid
    res.json({ ok: true });
  } finally { client.release(); }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('Exchange backend listening on', PORT));
