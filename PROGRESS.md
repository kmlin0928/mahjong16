# 任務：麻將網頁版競賽模式

## 架構決策
- **後端**：FastAPI + WebSocket（遊戲狀態推送）
- **前端**：原生 HTML / CSS / JS（無框架）
- **核心**：`main()` 的 stdin/stdout 互動模式**完整保留**；另新增 `GameSession` 狀態機供網頁後端使用
- **啟動**：終端機選單（← 指令模式 / → 網頁模式），使用 `readchar` 套件捕捉方向鍵

## 版面設計（網頁模式）
```
┌─────────────────────────────┐
│       對家（上，橫排）         │
│  棄牌  面牌  [背面×16]        │
├──────┬──────────────┬────────┤
│ 上家  │  【中央提示】  │  下家  │
│（左  │  吃/碰/槓/胡  │（右   │
│ 直排）│              │ 直排）│
├──────┴──────────────┴────────┤
│    你（下，可點擊按鈕出牌）      │
│  面牌  棄牌  [牌名按鈕×17]     │
└─────────────────────────────┘
```

## 任務清單

### 1. [v] 啟動模式選單（方向鍵選擇）
- 檔案：`mahjong.py`（`__main__` 區塊）
- 摘要：
  - 顯示「← 指令模式　→ 網頁模式」提示
  - 使用 `readchar` 捕捉方向鍵（`readchar.readkey()`）
  - 左鍵 → 執行原有 while 迴圈（`main()`）
  - 右鍵 → 啟動 FastAPI server（`uvicorn web_mahjong:app`）並開啟瀏覽器

### 2. [v] 新增 GameSession 狀態機（平行於 main()）
- 檔案：`mahjong.py`（新增 `GameSession` 類別，不修改 `main()`）
- 摘要：
  狀態機方法（每次呼叫推進遊戲並回傳 `GameState`）：
  - `start(contest: bool)` → 初始化牌局
  - `next_ai_turns()` → 推進 AI 回合直到需要人類決策
  - `human_discard(idx: int)` → 人類出牌
  - `human_action(action: str)` → 回應 `"win"` / `"pon"` / `"chi_N"` / `"kong"` / `"pass"`

### 3. [v] 定義 GameState dataclass
- 檔案：`mahjong.py`（`GameSession` 正上方）
- 摘要：可 JSON 序列化，包含：
  - `phase`: `"ai_turn"` | `"human_discard"` | `"prompt"` | `"game_over"`
  - `your_hand`: `list[str]`（牌名列表）
  - `hand_counts`: `list[int]`（四家手牌張數，供競賽模式隱藏 AI 牌名）
  - `melds`: `list[list[list[str]]]`（四家各副露組）
  - `discards`: `list[list[str]]`（四家棄牌）
  - `log`: `list[str]`（本輪事件文字）
  - `prompt`: `dict | None`（提示類型與選項）
  - `winner`: `str | None`、`scores`: `list[tuple[str,int]] | None`

### 4. [ ] 建立 FastAPI 後端
- 檔案：`web_mahjong.py`（新建）
- 摘要：
  - `GET /` → 回傳 `static/index.html`
  - `POST /new_game?contest=true` → 建立 `GameSession`，推進至首個人類回合，回傳 `GameState`
  - `POST /discard?idx=N` → 人類出牌，推進至下個人類回合，回傳 `GameState`
  - `POST /action?type=win|pon|chi_0|kong|pass` → 回應提示，回傳 `GameState`
  - `WebSocket /ws` → 推送 AI 回合 log 串流（`log` 欄位逐行送出）

### 5. [ ] 前端基礎版面（四方位 CSS）
- 檔案：`static/index.html`、`static/style.css`（新建）
- 摘要：CSS Grid 佈局：
  - 上區：對家橫排（背面色塊 + 面牌 + 棄牌）
  - 左區：上家直排（`writing-mode: vertical-rl` 旋轉）
  - 右區：下家直排（同左）
  - 下區：你的手牌（`<button>` 排列，牌名標示）
  - 中央：提示卡片區（預設隱藏）

### 6. [ ] 手牌、棄牌、面牌渲染（JS）
- 檔案：`static/app.js`（新建）
- 摘要：
  - `renderState(state)` 根據 `GameState` 更新所有 DOM 區域
  - 你的手牌：點擊 `<button>` → `POST /discard?idx=N`
  - AI 手牌：顯示背面色塊＋張數（競賽模式不顯示牌名）
  - 棄牌區、面牌區各方位渲染
  - WebSocket 接收 log 並逐行附加至事件記錄欄

### 7. [ ] 中央提示與吃碰槓胡互動
- 檔案：`static/app.js`、`static/style.css`
- 摘要：
  - `state.prompt != null` 時顯示提示卡片
  - `win` → 「胡！/ 跳過」按鈕
  - `pon` → 「碰 / 跳過」按鈕
  - `chi` → 列出各吃法按鈕（`chi_0`、`chi_1`…）+ 跳過
  - `kong` → 「槓 / 跳過」按鈕
  - 點擊後 `POST /action?type=…`，刷新狀態

## 驗收條件
- 執行 `uv run mahjong.py`，方向鍵左 → 進入指令模式（原有行為不變）
- 方向鍵右 → 開啟瀏覽器，顯示牌桌，可進行一局完整對局
- 競賽模式下 AI 手牌僅顯示背面色塊

## 狀態更新規則
- `[ ]` 未開始
- `[/]` 進行中
- `[v]` 完成
