/* app.js — 麻將競賽模式前端 */

let _state = null;
let _waiting = false;  // 避免重複送出

// ── API 呼叫 ────────────────────────────────────────────────
async function api(path, params = {}) {
  const url = new URL(path, location.href);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

// ── 遊戲流程 ────────────────────────────────────────────────
async function startGame() {
  document.getElementById('start-overlay').style.display = 'none';
  document.getElementById('gameover-banner').style.display = 'none';
  const state = await api('/new_game', { contest: true });
  renderState(state);
}

async function sendDiscard(idx) {
  if (_waiting) return;
  _waiting = true;
  setHandEnabled(false);
  const state = await api('/discard', { idx });
  _waiting = false;
  renderState(state);
}

async function sendAction(type) {
  if (_waiting) return;
  _waiting = true;
  const state = await api('/action', { type });
  _waiting = false;
  renderState(state);
}

// ── 渲染主控 ────────────────────────────────────────────────
function renderState(state) {
  _state = state;

  updateWindBadge(state);
  renderAllZones(state);
  renderLog(state.log);

  if (state.phase === 'game_over') {
    showGameOver(state);
    return;
  }

  if (state.phase === 'prompt' && state.prompt) {
    showPrompt(state.prompt);
    setHandEnabled(false);
  } else {
    hidePrompt();
    setHandEnabled(state.phase === 'human_discard');
  }
}

// ── 風圈門風 ────────────────────────────────────────────────
function updateWindBadge(state) {
  const humanSeatWind = (state.seat_winds && state.seat_winds.length > 0)
    ? state.seat_winds[0]   // HUMAN_PLAYER = 0
    : '?';
  const gameWind = state.game_wind || '?';
  document.getElementById('wind-game').textContent = gameWind;
  document.getElementById('wind-seat').textContent = humanSeatWind;
}

// ── 四方位渲染 ───────────────────────────────────────────────
// player indices: 0=你, 1=下家(右), 2=對家(上), 3=上家(左)
function renderAllZones(state) {
  // 你（下區）
  renderHandButtons('bottom-hand', state.your_hand, state.phase === 'human_discard');
  renderTiles('bottom-melds', flatMelds(state.melds[0]));
  renderDiscards('bottom-discards', state.discards[0]);

  // 對家（上區）idx=2
  renderBackTiles('top-hand', state.hand_counts[2]);
  renderTiles('top-melds', flatMelds(state.melds[2]));
  renderDiscards('top-discards', state.discards[2]);

  // 上家（左區）idx=3
  renderBackTiles('left-hand', state.hand_counts[3]);
  renderTiles('left-melds', flatMelds(state.melds[3]));
  renderDiscards('left-discards', state.discards[3]);

  // 下家（右區）idx=1
  renderBackTiles('right-hand', state.hand_counts[1]);
  renderTiles('right-melds', flatMelds(state.melds[1]));
  renderDiscards('right-discards', state.discards[1]);
}

function flatMelds(melds) {
  return melds.flatMap(m => m);
}

function makeTileEl(text, cls = '') {
  const el = document.createElement('div');
  el.className = 'tile' + (cls ? ' ' + cls : '');
  el.textContent = text;
  return el;
}

function renderTiles(id, tiles) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  tiles.forEach(t => el.appendChild(makeTileEl(t)));
}

function renderDiscards(id, tiles) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  tiles.forEach(t => el.appendChild(makeTileEl(t, 'discard')));
}

function renderBackTiles(id, count) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  for (let i = 0; i < count; i++) {
    el.appendChild(makeTileEl('', 'back'));
  }
}

function renderHandButtons(id, tiles, enabled) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  tiles.forEach((t, i) => {
    const btn = document.createElement('button');
    btn.className = 'tile-btn';
    btn.textContent = t;
    btn.disabled = !enabled;
    btn.onclick = () => sendDiscard(i);
    el.appendChild(btn);
  });
}

function setHandEnabled(enabled) {
  document.querySelectorAll('#bottom-hand .tile-btn').forEach(b => {
    b.disabled = !enabled;
  });
}

// ── 提示卡 ───────────────────────────────────────────────────
function showPrompt(prompt) {
  const card = document.getElementById('prompt-card');
  const title = document.getElementById('prompt-title');
  const btns = document.getElementById('prompt-buttons');
  card.classList.remove('hidden');

  const labels = {
    win_tsumo: '自摸！',
    win_ron: `胡！（${prompt.tile}）`,
    rob_kong: `搶槓！（${prompt.tile}）`,
    add_kong: `加槓 ${prompt.tile}`,
    kong: `槓 ${prompt.tile}`,
    pon: `碰 ${prompt.tile}`,
    chi: `吃 ${prompt.tile}`,
  };
  title.textContent = labels[prompt.type] ?? prompt.type;
  btns.innerHTML = '';

  if (prompt.type === 'chi' && prompt.chi_options) {
    prompt.chi_options.forEach((opt, i) => {
      addBtn(btns, opt.join(''), () => sendAction(`chi:${i}`));
    });
  } else {
    addBtn(btns, '✓ 接受', () => sendAction('y'));
  }
  addBtn(btns, '✗ 跳過', () => sendAction('n'));
}

function hidePrompt() {
  document.getElementById('prompt-card').classList.add('hidden');
}

function addBtn(container, label, onclick) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.onclick = onclick;
  container.appendChild(btn);
}

// ── 事件 log ─────────────────────────────────────────────────
function renderLog(lines) {
  const box = document.getElementById('log-box');
  box.innerHTML = '';
  // 最新在最上（column-reverse）
  lines.forEach(l => {
    const p = document.createElement('p');
    p.textContent = l;
    box.appendChild(p);
  });
}

// ── 遊戲結束 ─────────────────────────────────────────────────
function showGameOver(state) {
  hidePrompt();
  const banner = document.getElementById('gameover-banner');
  banner.style.display = 'block';
  banner.querySelector('h2').textContent = state.winner
    ? `${state.winner} 胡牌！`
    : '和局';
  const sc = banner.querySelector('.scores');
  if (state.scores && state.scores.length) {
    sc.textContent = state.scores.map(([label, pts]) => `${label} ${pts}台`).join('　');
  } else {
    sc.textContent = '';
  }
}

// ── 初始化 ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // gameover banner（動態建立，避免 HTML 冗餘）
  if (!document.getElementById('gameover-banner')) {
    const banner = document.createElement('div');
    banner.id = 'gameover-banner';
    banner.innerHTML = `
      <h2></h2>
      <div class="scores"></div>
      <button onclick="startGame()">再來一局</button>`;
    document.body.appendChild(banner);
  }
});
