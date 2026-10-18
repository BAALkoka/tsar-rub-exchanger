// Простая игра "Бегущий царь собирает монеты"
// Контроль: пробел / стрелка вверх / клик/тап

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const scoreEl = document.getElementById('score');

const W = canvas.width;
const H = canvas.height;

let gameRunning = false;
let gameOver = false;
let score = 0;
let tick = 0;

// Платформа
const groundY = H - 80;

// Игрок (царь)
const player = {
  x: 120,
  y: groundY - 48,
  w: 40,
  h: 48,
  vy: 0,
  jumpPower: -13,
  gravity: 0.7,
  onGround: true,
  color: '#234db3'
};

// Массивы для монет и препятствий
let coins = [];
let obstacles = [];

function reset() {
  gameRunning = true;
  gameOver = false;
  score = 0;
  tick = 0;
  coins = [];
  obstacles = [];
  player.y = groundY - player.h;
  player.vy = 0;
  player.onGround = true;
  updateHud();
}

// Создаёт монету
function spawnCoin() {
  const size = 14;
  const x = W + Math.random() * 200;
  const y = groundY - 20 - Math.random() * 120;
  coins.push({ x, y, r: size/2, collected: false, speed: 4 + Math.random()*2 });
}

// Создаёт препятствие
function spawnObstacle() {
  const h = 30 + Math.random()*30;
  const w = 20 + Math.random()*20;
  const x = W + Math.random() * 200;
  const y = groundY - h;
  obstacles.push({ x, y, w, h, speed: 5 });
}

// Обновление HUD
function updateHud() {
  scoreEl.textContent = 'Счёт: ' + score;
}

// Управление прыжком
function jump() {
  if (!gameRunning) {
    reset();
    requestAnimationFrame(update);
    return;
  }
  if (!player.onGround) return;
  player.vy = player.jumpPower;
  player.onGround = false;
}

// Обработчики ввода
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' || e.code === 'ArrowUp') {
    e.preventDefault();
    jump();
  }
});
canvas.addEventListener('click', () => {
  if (gameOver) reset();
  else jump();
});
canvas.addEventListener('touchstart', (e) => {
  e.preventDefault();
  if (gameOver) reset();
  else jump();
}, {passive:false});

// Коллизия прямоугольника и круга
function rectCircleColliding(rect, circle) {
  const distX = Math.abs(circle.x - rect.x - rect.w/2);
  const distY = Math.abs(circle.y - rect.y - rect.h/2);

  if (distX > (rect.w/2 + circle.r)) return false;
  if (distY > (rect.h/2 + circle.r)) return false;
  if (distX <= (rect.w/2)) return true;
  if (distY <= (rect.h/2)) return true;

  const dx = distX - rect.w/2;
  const dy = distY - rect.h/2;
  return (dx*dx + dy*dy <= circle.r*circle.r);
}

// Главный цикл
function update() {
  if (!gameRunning) {
    drawStart();
    return;
  }
  tick++;

  // Спавн монет и препятствий
  if (tick % 80 === 0) spawnCoin();
  if (tick % 220 === 0) spawnObstacle();
  if (Math.random() < 0.01) spawnCoin();

  // Обновляем игрока
  player.vy += player.gravity;
  player.y += player.vy;

  if (player.y + player.h >= groundY) {
    player.y = groundY - player.h;
    player.vy = 0;
    player.onGround = true;
  }

  // Перемещение монет
  for (let i = coins.length-1; i >= 0; i--) {
    const c = coins[i];
    c.x -= c.speed;
    // сбор
    if (rectCircleColliding(player, c) && !c.collected) {
      c.collected = true;
      score += 1;
      updateHud();
      // эффект: удалить монету
      coins.splice(i,1);
      continue;
    }
    // удаляем если ушла
    if (c.x + c.r < -50) coins.splice(i,1);
  }

  // Перемещение препятствий
  for (let i = obstacles.length-1; i >= 0; i--) {
    const o = obstacles[i];
    o.x -= o.speed;
    // столкновение (AABB)
    if (!(player.x + player.w < o.x || player.x > o.x + o.w || player.y + player.h < o.y || player.y > o.y + o.h)) {
      // столкновение — конец игры
      gameOver = true;
      gameRunning = false;
    }
    if (o.x + o.w < -50) obstacles.splice(i,1);
  }

  draw();

  if (!gameOver) requestAnimationFrame(update);
  else drawGameOver();
}

// Отрисовка сцены
function draw() {
  // фон
  ctx.clearRect(0,0,W,H);

  // небо (градиент уже в CSS, но нарисуем немного облаков)
  // земля
  ctx.fillStyle = '#5aa65a';
  ctx.fillRect(0, groundY, W, H - groundY);

  // платформа линия
  ctx.strokeStyle = '#2f8a2f';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(0, groundY);
  ctx.lineTo(W, groundY);
  ctx.stroke();

  // игрок - царь (прямоугольник + корона)
  ctx.fillStyle = player.color;
  ctx.fillRect(player.x, player.y, player.w, player.h);

  // корона
  const crownW = player.w;
  ctx.fillStyle = '#ffd700';
  const cx = player.x + player.w/2;
  const cy = player.y - 6;
  ctx.beginPath();
  ctx.moveTo(player.x + 6, player.y);
  ctx.lineTo(player.x + crownW*0.3, player.y - 12);
  ctx.lineTo(player.x + crownW*0.5, player.y - 6);
  ctx.lineTo(player.x + crownW*0.7, player.y - 12);
  ctx.lineTo(player.x + crownW - 6, player.y);
  ctx.closePath();
  ctx.fill();
  // глаза (для настроения)
  ctx.fillStyle = '#fff';
  ctx.fillRect(player.x + 8, player.y + 14, 6, 6);
  ctx.fillRect(player.x + player.w - 14, player.y + 14, 6, 6);
  ctx.fillStyle = '#000';
  ctx.fillRect(player.x + 10, player.y + 16, 2, 2);
  ctx.fillRect(player.x + player.w - 12, player.y + 16, 2, 2);

  // монеты
  for (const c of coins) {
    // отблеск
    ctx.beginPath();
    ctx.fillStyle = '#ffdf4a';
    ctx.arc(c.x, c.y, c.r, 0, Math.PI*2);
    ctx.fill();
    ctx.strokeStyle = '#e6b800';
    ctx.lineWidth = 2;
    ctx.stroke();
    // блеск
    ctx.beginPath();
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    ctx.ellipse(c.x - c.r*0.3, c.y - c.r*0.3, c.r*0.35, c.r*0.55, -0.5, 0, Math.PI*2);
    ctx.fill();
  }

  // препятствия (камни)
  for (const o of obstacles) {
    ctx.fillStyle = '#6b6b6b';
    ctx.fillRect(o.x, o.y, o.w, o.h);
    ctx.strokeStyle = '#4a4a4a';
    ctx.strokeRect(o.x, o.y, o.w, o.h);
  }

  // табло очков
  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  ctx.fillRect(10, 10, 140, 28);
  ctx.fillStyle = '#fff';
  ctx.font = '16px sans-serif';
  ctx.fillText('Счёт: ' + score, 18, 30);
}

// Экран старта
function drawStart() {
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle = 'rgba(0,0,0,0.05)';
  ctx.fillRect(0,0,W,H);
  ctx.fillStyle = '#222';
  ctx.font = '24px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Нажмите пробел или тап, чтобы начать', W/2, H/2 - 20);
  ctx.font = '16px sans-serif';
  ctx.fillText('Собирайте монеты — избегайте препятствий', W/2, H/2 + 12);
}

// Экран Game Over
function drawGameOver() {
  draw();
  ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.font = '36px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Game Over', W/2, H/2 - 20);
  ctx.font = '20px sans-serif';
  ctx.fillText('Ваш счёт: ' + score, W/2, H/2 + 12);
  ctx.font = '16px sans-serif';
  ctx.fillText('Кликните для перезапуска', W/2, H/2 + 48);
}

// Запуск
updateHud();
drawStart();

// Авто-старт по клику
canvas.addEventListener('dblclick', () => { if (!gameRunning) { reset(); requestAnimationFrame(update); } });

// Для совместимости: начнём анимационный цикл и будем запускать update по запросу
requestAnimationFrame(function loop() {
  if (gameRunning) requestAnimationFrame(loop);
});
