/* app.js — 麻將競賽模式前端（WebSocket 串流版） */

let _state   = null;
let _waiting = false;   // 避免重複送出
let _ws      = null;    // WebSocket 連線
let _seat    = 0;       // 本連線綁定的席位（多人連線模式由伺服器 hello 指定）
let _lobby   = null;    // 多人連線大廳狀態；單人模式維持 null

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
  '梅':'🀢','蘭':'🀣','竹':'🀤','菊':'🀥',
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
    } else if (msg.t === 'reset') {
      // 其他玩家（或自己）開了新局：清空事件並收起覆蓋層
      document.getElementById('log-box').innerHTML = '';
      document.getElementById('start-overlay').style.display = 'none';
      document.getElementById('gameover-banner').style.display = 'none';
      hidePrompt();
      setHandEnabled(false);
    } else if (msg.t === 'hello') {
      // 多人連線模式：伺服器告知本連接埠綁定的席位
      _seat  = msg.v.seat ?? 0;
      _lobby = _lobby || {};
      Object.assign(_lobby, msg.v);
      renderSeatBadge();
      renderLobby();
    } else if (msg.t === 'lobby') {
      _lobby = Object.assign(_lobby || {}, msg.v);
      renderLobby();
    } else if (msg.t === 'error') {
      console.error('WS error:', msg.v);
      appendLog(`⚠ ${msg.v}`);
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

// ── 視角旋轉：本家永遠在下方，順時針為 下家→對家→上家 ──────────
/** 回傳 [下, 右, 上, 左] 各方位對應的絕對席位編號。 */
function zoneSeats(me) {
  const m = ((me ?? 0) % 4 + 4) % 4;
  return [m, (m + 1) % 4, (m + 2) % 4, (m + 3) % 4];
}

// ── 席位徽章與大廳（僅多人連線模式） ─────────────────────────────
function renderSeatBadge() {
  const el = document.getElementById('seat-badge');
  if (!el) return;
  if (!_lobby) { el.classList.add('hidden'); return; }
  const wind = (_state && _state.seat_winds && _state.seat_winds.length)
    ? _state.seat_winds[_seat] : null;
  el.textContent = wind ? `你：席位 ${_seat}（${wind}家）` : `你：席位 ${_seat}`;
  el.classList.remove('hidden');
}

function renderLobby() {
  const el = document.getElementById('lobby-panel');
  if (!el || !_lobby) return;
  const humans    = _lobby.human_seats || [];
  const connected = _lobby.connected   || [];
  const ports     = _lobby.seat_ports  || {};
  const rows = [];
  for (let s = 0; s < 4; s++) {
    let who, cls;
    if (!humans.includes(s)) {
      who = 'AI'; cls = 'lobby-ai';
    } else if (connected.includes(s)) {
      who = s === _seat ? '你（已連線）' : '玩家（已連線）'; cls = 'lobby-on';
    } else {
      who = '等待連線…'; cls = 'lobby-off';
    }
    const port = ports[String(s)] ? `　:${ports[String(s)]}` : '';
    rows.push(`<div class="lobby-row ${cls}">席位 ${s}　${who}${port}</div>`);
  }
  el.innerHTML = `<div class="lobby-title">連線狀態</div>${rows.join('')}`;
  el.classList.remove('hidden');
}

// ── 遊戲流程 ────────────────────────────────────────────────
function startGame() {
  _startNewGame();
}

// 圈風循環（東→南→西→北→東...）
const WIND_CYCLE = ['東', '南', '西', '北'];

function _startNewGame(dealerIdx = null, consecutive = 0, seatWinds = null, roundWind = null) {
  document.getElementById('start-overlay').style.display = 'none';
  document.getElementById('gameover-banner').style.display = 'none';
  document.getElementById('log-box').innerHTML = '';
  _waiting = true;
  setHandEnabled(false);
  hidePrompt();
  const cmd = { cmd: 'new_game', contest: true, consecutive };
  if (typeof dealerIdx === 'number') cmd.dealer_idx = dealerIdx;
  if (seatWinds !== null) cmd.seat_winds = seatWinds;
  if (roundWind !== null) cmd.game_round_wind = roundWind;
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
  const seats  = zoneSeats(state.your_seat ?? _seat);
  DEALER_BADGE_IDS.forEach((id, zone) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (seats[zone] === state.dealer_idx) {
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
  if (typeof state.your_seat === 'number') _seat = state.your_seat;
  // 牌局進行中 → 收起開始／結束覆蓋層（別家開新局時本家也要同步）
  if (state.phase !== 'game_over') {
    document.getElementById('start-overlay').style.display = 'none';
    document.getElementById('gameover-banner').style.display = 'none';
  }
  renderSeatBadge();
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
  updateTurnHint(state);
}

// ── 輪到誰的提示（多人連線模式） ──────────────────────────────────
function updateTurnHint(state) {
  const el = document.getElementById('turn-hint');
  if (!el) return;
  const cur = state.current_seat ?? -1;
  if (cur < 0 || state.phase === 'game_over') {
    el.classList.add('hidden');
    return;
  }
  const winds = state.seat_winds || [];
  if (cur === (state.your_seat ?? _seat)) {
    el.textContent = '輪到你';
    el.classList.add('my-turn');
  } else {
    el.textContent = `等待 ${winds[cur] || `席位 ${cur}`} 行動…`;
    el.classList.remove('my-turn');
  }
  el.classList.remove('hidden');
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
  const gameRoundWind = state.game_round_wind || state.game_wind || '?';
  const winds         = state.seat_winds || [];
  const dealerWind    = (winds.length > 0 && state.dealer_idx >= 0)
    ? winds[state.dealer_idx] : '?';
  document.getElementById('wind-game').textContent  = gameRoundWind + '風';
  document.getElementById('wind-round').textContent = dealerWind + '局';

  // 各方位門風標籤（依本家視角旋轉，本家永遠在下方）
  const labels = ['label-bottom', 'label-right', 'label-top', 'label-left'];
  const seats  = zoneSeats(state.your_seat ?? _seat);
  labels.forEach((id, zone) => {
    const el = document.getElementById(id);
    if (!el) return;
    const s = seats[zone];
    const mine = (s === (state.your_seat ?? _seat)) ? '（你）' : '';
    el.textContent = (winds[s] || '?') + mine;
  });
}

// ── 四方位渲染 ───────────────────────────────────────────────
function renderAllZones(state) {
  const bonus = state.bonus || [[], [], [], []];
  // [下, 右, 上, 左] → 絕對席位；本家（your_seat）永遠畫在下方
  const [sBottom, sRight, sTop, sLeft] = zoneSeats(state.your_seat ?? _seat);

  renderHandButtons('bottom-hand', state.your_hand, state.phase === 'human_discard', state.drawn_tile_idx ?? null);
  renderTiles('bottom-melds', flatMelds(state.melds[sBottom]));
  renderDiscards('bottom-discards', state.discards[sBottom]);
  renderDiscards('bottom-bonus', bonus[sBottom]);

  renderBackTiles('top-hand', state.hand_counts[sTop]);
  renderTiles('top-melds', flatMelds(state.melds[sTop]));
  renderDiscards('top-discards', state.discards[sTop]);
  renderDiscards('top-bonus', bonus[sTop]);

  renderBackTiles('left-hand', state.hand_counts[sLeft]);
  renderTiles('left-melds', flatMelds(state.melds[sLeft]));
  renderDiscards('left-discards', state.discards[sLeft]);
  renderDiscards('left-bonus', bonus[sLeft]);

  renderBackTiles('right-hand', state.hand_counts[sRight]);
  renderTiles('right-melds', flatMelds(state.melds[sRight]));
  renderDiscards('right-discards', state.discards[sRight]);
  renderDiscards('right-bonus', bonus[sRight]);
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

function renderHandButtons(id, tiles, enabled, drawnIdx = null) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  tiles.forEach((t, i) => {
    const btn = document.createElement('button');
    btn.className = 'tile-btn';
    const suit = suitOf(t);
    if (suit) btn.dataset.suit = suit;
    if (i === drawnIdx) btn.classList.add('drawn');
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
const _LOG_CLASSES = [
  { key: '補花', cls: 'log-bonus' },
  { key: '打',   cls: 'log-discard' },
  { key: '吃',   cls: 'log-chi' },
  { key: '碰',   cls: 'log-pon' },
  { key: '槓',   cls: 'log-kong' },
];

function appendLog(line) {
  const box = document.getElementById('log-box');
  // 移除最新行舊標記
  box.querySelectorAll('p.latest').forEach(p => p.classList.remove('latest'));
  const p = document.createElement('p');
  p.textContent = line;
  p.className = 'latest';
  const match = _LOG_CLASSES.find(({ key }) => line.includes(key));
  if (match) p.classList.add(match.cls);
  box.appendChild(p);
  box.scrollTop = box.scrollHeight;
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

  // 四家手牌
  const handsEl = document.getElementById('gameover-hands');
  handsEl.innerHTML = '';
  if (state.all_hands && state.seat_winds) {
    state.all_hands.forEach((hand, i) => {
      const row = document.createElement('div');
      row.className = 'hand-row';
      const lbl = document.createElement('span');
      lbl.className = 'hand-label';
      lbl.textContent = state.seat_winds[i] + '：';
      row.appendChild(lbl);
      // 面牌（副露組合）
      const melds = flatMelds(state.melds[i]);
      if (melds.length) {
        melds.forEach(t => row.appendChild(makeTileEl(t)));
        const sep = document.createElement('span');
        sep.className = 'meld-sep';
        row.appendChild(sep);
      }
      hand.forEach(t => row.appendChild(makeTileEl(t)));
      // 花牌
      const bonus = (state.bonus && state.bonus[i]) || [];
      if (bonus.length) {
        const sep2 = document.createElement('span');
        sep2.className = 'meld-sep';
        row.appendChild(sep2);
        bonus.forEach(t => row.appendChild(makeTileEl(t)));
      }
      handsEl.appendChild(row);
    });
  }

  // 按鈕
  btnArea.innerHTML = '';
  if (isConsec) {
    // 連莊：莊家不變，consecutive+1，座次與圈風不變
    addGameBtn(btnArea, '連莊！', () =>
      _startNewGame(state.dealer_idx, state.consecutive + 1, state.seat_winds, state.game_round_wind));
    addGameBtn(btnArea, '重置新局', () => _startNewGame());
  } else {
    // 下莊：dealer 前進，座次與圈風不變
    const nextDealer = (state.dealer_idx + 1) % 4;
    addGameBtn(btnArea, '下一局', () =>
      _startNewGame(nextDealer, 0, state.seat_winds, state.game_round_wind));
    addGameBtn(btnArea, '重置新局', () => _startNewGame());
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
  // 多人連線模式：先問伺服器本連接埠綁哪一席（單人模式回 404，忽略即可）
  fetch('/seat')
    .then(r => (r.ok ? r.json() : null))
    .then(info => {
      if (!info) return;
      _seat  = info.seat ?? 0;
      _lobby = Object.assign(_lobby || {}, info);
      renderSeatBadge();
      renderLobby();
    })
    .catch(() => {});
  connectWS();
});
