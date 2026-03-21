/* app.js — 麻將競賽模式前端（WebSocket 串流版） */

let _state   = null;
let _waiting = false;   // 避免重複送出
let _ws      = null;    // WebSocket 連線

// ── Unicode 麻將符號對照表（U+1F000–U+1F02B） ─────────────────
const TILE_UNICODE = {
  // 筒（Circles）1–9: U+1F019–U+1F021
  '1筒':'🀙','2筒':'🀚','3筒':'🀛','4筒':'🀜','5筒':'🀝',
  '6筒':'🀞','7筒':'🀟','8筒':'🀠','9筒':'🀡',
  // 索（Bamboo）1–9: U+1F010–U+1F018
  '1索':'🀐','2索':'🀑','3索':'🀒','4索':'🀓','5索':'🀔',
  '6索':'🀕','7索':'🀖','8索':'🀗','9索':'🀘',
  // 萬（Characters）1–9: U+1F007–U+1F00F
  '1萬':'🀇','2萬':'🀈','3萬':'🀉','4萬':'🀊','5萬':'🀋',
  '6萬':'🀌','7萬':'🀍','8萬':'🀎','9萬':'🀏',
  // 風牌
  '東':'🀀','南':'🀁','西':'🀂','北':'🀃',
  // 三元牌
  '中':'🀄','發':'🀅','白':'🀆',
  // 花牌: U+1F022–U+1F029
  '梅':'🀢','蘭':'🀣','菊':'🀤','竹':'🀥',
  '春':'🀦','夏':'🀧','秋':'🀨','冬':'🀩',
};

/** 回傳牌片的 { emoji, label }。找不到 Unicode 時 emoji 留空。 */
function tileContent(name) {
  return { emoji: TILE_UNICODE[name] ?? '', label: name };
}

// ── 牌面花色判定 ─────────────────────────────────────────────
function suitOf(tileName) {
  if (!tileName) return '';
  if (tileName.includes('萬')) return 'wan';
  if (tileName.includes('筒')) return 'tong';
  if (tileName.includes('索')) return 'suo';
  if (['東','南','西','北'].some(w => tileName.includes(w))) return 'wind';
  if (['中','發','白'].some(w => tileName.includes(w))) return 'drag';
  if (['春','夏','秋','冬','梅','蘭','竹','菊'].some(w => tileName.includes(w))) return 'flower';
  return '';
}

// ── WebSocket 管理 ───────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  _ws = new WebSocket(`${proto}//${location.host}/ws`);

  _ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.t === 'log') {
      appendLog(msg.v);
    } else if (msg.t === 'state') {
      _waiting = false;
      renderState(msg.v);
    } else if (msg.t === 'error') {
      console.error('WS error:', msg.v);
      _waiting = false;
    }
  };

  _ws.onclose = () => {
    _ws = null;
    // 2 秒後重連
    setTimeout(connectWS, 2000);
  };

  _ws.onerror = () => _ws.close();
}

function wsSend(obj) {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) {
    console.warn('WS 未連線，等待重連後重試');
    setTimeout(() => wsSend(obj), 300);
    return;
  }
  _ws.send(JSON.stringify(obj));
}

// ── 遊戲流程 ────────────────────────────────────────────────
function startGame() {
  _startNewGame();
}

function _startNewGame(dealerIdx = null, consecutive = 0) {
  document.getElementById('start-overlay').style.display = 'none';
  document.getElementById('gameover-banner').style.display = 'none';
  document.getElementById('log-box').innerHTML = '';
  _waiting = true;
  setHandEnabled(false);
  hidePrompt();
  const cmd = { cmd: 'new_game', contest: true, consecutive };
  if (dealerIdx !== null) cmd.dealer_idx = dealerIdx;
  wsSend(cmd);
}

function sendDiscard(idx) {
  if (_waiting) return;
  _waiting = true;
  setHandEnabled(false);
  wsSend({ cmd: 'discard', idx });
}

function sendAction(action) {
  if (_waiting) return;
  _waiting = true;
  hidePrompt();
  wsSend({ cmd: 'action', action });
}

// ── 莊家連莊標示 ─────────────────────────────────────────────
const DEALER_BADGE_IDS = ['dealer-bottom', 'dealer-right', 'dealer-top', 'dealer-left'];

function updateDealerBadge(state) {
  const consec = state.consecutive ?? 0;
  DEALER_BADGE_IDS.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (i === state.dealer_idx) {
      el.textContent = `連莊${consec}`;
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  });
}

// ── 渲染主控 ────────────────────────────────────────────────
function renderState(state) {
  _state = state;
  updateWindBadge(state);
  updateDeckCount(state);
  updateDealerBadge(state);
  renderAllZones(state);
  // log 已由 WS 逐行推送，不在此覆蓋

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

// ── 剩餘牌數 ────────────────────────────────────────────────
function updateDeckCount(state) {
  const el = document.getElementById('deck-count');
  if (!el) return;
  const n = state.deck_remaining ?? 0;
  el.textContent = `剩 ${n} 張`;
  el.classList.toggle('danger', n <= 10);
}

// ── 風圈門風 ────────────────────────────────────────────────
function updateWindBadge(state) {
  const gameWind   = state.game_wind || '?';
  const winds      = state.seat_winds || [];
  const dealerWind = (winds.length > 0 && state.dealer_idx >= 0)
    ? winds[state.dealer_idx] : '?';
  document.getElementById('wind-game').textContent  = gameWind + '風';
  document.getElementById('wind-round').textContent = dealerWind + '局';

  // 各方位門風標籤
  const labels = ['label-bottom', 'label-right', 'label-top', 'label-left'];
  labels.forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) el.textContent = winds[i] || '?';
  });
}

// ── 四方位渲染 ───────────────────────────────────────────────
function renderAllZones(state) {
  const bonus = state.bonus || [[], [], [], []];

  renderHandButtons('bottom-hand', state.your_hand, state.phase === 'human_discard');
  renderTiles('bottom-melds', flatMelds(state.melds[0]));
  renderDiscards('bottom-discards', state.discards[0]);
  renderDiscards('bottom-bonus', bonus[0]);

  renderBackTiles('top-hand', state.hand_counts[2]);
  renderTiles('top-melds', flatMelds(state.melds[2]));
  renderDiscards('top-discards', state.discards[2]);
  renderDiscards('top-bonus', bonus[2]);

  renderBackTiles('left-hand', state.hand_counts[3]);
  renderTiles('left-melds', flatMelds(state.melds[3]));
  renderDiscards('left-discards', state.discards[3]);
  renderDiscards('left-bonus', bonus[3]);

  renderBackTiles('right-hand', state.hand_counts[1]);
  renderTiles('right-melds', flatMelds(state.melds[1]));
  renderDiscards('right-discards', state.discards[1]);
  renderDiscards('right-bonus', bonus[1]);
}

function flatMelds(melds) {
  return melds.flatMap(m => m);
}

// ── 牌片建立 ────────────────────────────────────────────────
function makeTileEl(text, extraClass = '') {
  const el = document.createElement('div');
  const suit = suitOf(text);
  el.className = 'tile' + (extraClass ? ' ' + extraClass : '') + (suit === 'flower' ? ' flower' : '');
  if (suit) el.dataset.suit = suit;
  if (!text) {
    // 背面牌：使用 Unicode 背面符號
    el.textContent = '🀫';
    el.classList.add('back');
    return el;
  }
  const { emoji, label } = tileContent(text);
  el.title = label;   // tooltip 顯示牌名
  if (emoji) {
    el.innerHTML = `<span class="tile-emoji">${emoji}</span><span class="tile-label">${label}</span>`;
  } else {
    el.textContent = label;
  }
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
  for (let i = 0; i < count; i++) el.appendChild(makeTileEl(''));
}

function renderHandButtons(id, tiles, enabled) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  tiles.forEach((t, i) => {
    const btn = document.createElement('button');
    btn.className = 'tile-btn';
    const suit = suitOf(t);
    if (suit) btn.dataset.suit = suit;
    btn.title = t;
    const { emoji, label } = tileContent(t);
    if (emoji) {
      btn.innerHTML = `<span class="tile-emoji">${emoji}</span><span class="tile-label">${label}</span>`;
    } else {
      btn.textContent = label;
    }
    btn.disabled = !enabled;
    btn.onclick = () => sendDiscard(i);
    el.appendChild(btn);
  });
}

function setHandEnabled(enabled) {
  document.querySelectorAll('#bottom-hand .tile-btn').forEach(b => { b.disabled = !enabled; });
}

// ── 提示卡 ───────────────────────────────────────────────────
function showPrompt(prompt) {
  const card  = document.getElementById('prompt-card');
  const title = document.getElementById('prompt-title');
  const btns  = document.getElementById('prompt-buttons');
  card.classList.remove('hidden');

  const labels = {
    win_tsumo: '自摸！',
    win_ron:   `胡！（${prompt.tile}）`,
    rob_kong:  `搶槓！（${prompt.tile}）`,
    add_kong:  `加槓 ${prompt.tile}`,
    kong:      `槓 ${prompt.tile}`,
    pon:       `碰 ${prompt.tile}`,
    chi:       `吃 ${prompt.tile}`,
  };
  title.textContent = labels[prompt.type] ?? prompt.type;
  btns.innerHTML = '';

  if (prompt.type === 'chi' && prompt.chi_options) {
    prompt.chi_options.forEach((opt, i) => addBtn(btns, opt.join(''), () => sendAction(`chi:${i}`)));
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

// ── 事件 log（逐行附加） ──────────────────────────────────────
function appendLog(line) {
  const box = document.getElementById('log-box');
  // 移除最新行舊標記
  box.querySelectorAll('p.latest').forEach(p => p.classList.remove('latest'));
  const p = document.createElement('p');
  p.textContent = line;
  p.className = 'latest';
  box.prepend(p);    // 最新在最上
}

// ── 遊戲結束 ─────────────────────────────────────────────────
function showGameOver(state) {
  hidePrompt();
  const banner  = document.getElementById('gameover-banner');
  const btnArea = document.getElementById('gameover-btns');
  banner.style.display = 'block';

  const dealerWind = (state.seat_winds && state.dealer_idx >= 0)
    ? state.seat_winds[state.dealer_idx] : null;
  const isConsec = state.winner === null || state.winner === dealerWind;

  // 標題
  let title = state.winner ? `${state.winner} 胡牌！` : '和局';
  if (isConsec && state.consecutive > 0) title += `（連莊 ${state.consecutive} 次）`;
  document.getElementById('gameover-title').textContent = title;

  // 台數
  const sc = document.getElementById('gameover-scores');
  sc.textContent = (state.scores && state.scores.length)
    ? state.scores.map(([label, pts]) => `${label}　${pts} 台`).join('　')
    : '';

  // 按鈕
  btnArea.innerHTML = '';
  if (isConsec) {
    // 連莊：莊家不變，consecutive+1
    addGameBtn(btnArea, '連莊！', () =>
      _startNewGame(state.dealer_idx, state.consecutive + 1));
    addGameBtn(btnArea, '新局', () => _startNewGame());
  } else {
    // 下莊：完全重啓，不帶入任何莊家資訊
    addGameBtn(btnArea, '新局', () => _startNewGame());
  }
}

function addGameBtn(container, label, onclick) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.onclick = onclick;
  container.appendChild(btn);
}

// ── Log 收合（手機用） ────────────────────────────────────────
function toggleLog() {
  const box = document.getElementById('log-box');
  const btn = document.getElementById('log-toggle');
  const collapsed = box.classList.toggle('collapsed');
  btn.textContent = collapsed ? '▼ 事件記錄' : '▲ 事件記錄';
}

// ── 初始化 ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  connectWS();
});
