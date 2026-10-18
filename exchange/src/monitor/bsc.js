<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Admin — Tsar Exchange</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #f5f7fb; color: #1d2a39; }
    h2 { margin-bottom: 12px; }
    .panel { background: white; border-radius: 10px; padding: 14px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 18px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px 8px; border-bottom: 1px solid #e7ebf4; text-align: left; }
    th { background: #eef4ff; }
    .btn { display: inline-block; padding: 7px 12px; background: #2d89ef; color: white; border: none; border-radius: 6px; cursor: pointer; }
    .btn.warn { background: #f39c12; }
    .muted { color: #5f6d7a; }
  </style>
</head>
<body>
  <h2>Админ: ордера</h2>
  <div class="panel">
    <div class="muted">Состояние сервиса: <span id="status">Загрузка…</span></div>
    <div id="ordersContainer"></div>
  </div>

  <h2>Выплаты</h2>
  <div class="panel">
    <div id="payoutsContainer"></div>
  </div>

  <script>
    async function loadHealth() {
      try {
        const r = await fetch('/health');
        const data = await r.json();
        document.getElementById('status').textContent = data.ok ? 'online' : 'offline';
      } catch (e) {
        document.getElementById('status').textContent = 'offline';
      }
    }

    async function loadOrders() {
      const r = await fetch('/api/admin/orders');
      const data = await r.json();
      const orders = data.orders || [];
      const rows = orders.map((o) => `
        <tr>
          <td>${o.id}</td>
          <td>${o.user_id}</td>
          <td>${o.network}</td>
          <td>${o.amount_tokens}</td>
          <td>${o.status}</td>
          <td><button class="btn" onclick="markPayout(${o.id}, ${o.amount_tokens})">Выплатить</button></td>
        </tr>
      `).join('');

      document.getElementById('ordersContainer').innerHTML = `
        <table>
          <thead>
            <tr>
              <th>ID</th><th>User</th><th>Network</th><th>Tokens</th><th>Status</th><th>Action</th>
            </tr>
          </thead>
          <tbody>${rows || '<tr><td colspan="6">Нет ордеров</td></tr>'}</tbody>
        </table>
      `;
    }

    async function loadPayouts() {
      const r = await fetch('/api/admin/payouts');
      const data = await r.json();
      const payouts = data.payouts || [];
      const rows = payouts.map((p) => `
        <tr>
          <td>${p.id}</td>
          <td>${p.order_id}</td>
          <td>${p.amount_rub}</td>
          <td>${p.provider}</td>
          <td>${p.status}</td>
        </tr>
      `).join('');

      document.getElementById('payoutsContainer').innerHTML = `
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Order</th><th>Amount RUB</th><th>Provider</th><th>Status</th>
            </tr>
          </thead>
          <tbody>${rows || '<tr><td colspan="5">Нет выплат</td></tr>'}</tbody>
        </table>
      `;
    }

    async function markPayout(orderId, amountRub) {
      const payload = {
        amountRub: amountRub,
        provider: 'manual'
      };
      const r = await fetch(`/api/admin/payouts/${orderId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if (!r.ok) {
        alert('Ошибка: ' + (data.error || 'unknown'));
        return;
      }
      alert('Выплата отмечена как выполненная');
      await loadOrders();
      await loadPayouts();
    }

    async function init() {
      await loadHealth();
      await loadOrders();
      await loadPayouts();
    }
    init();
  </script>
</body>
</html>
