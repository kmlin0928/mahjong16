# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# 文件撰寫規則

用正體中文撰寫相關文件，回應都使用正體中文。

撰寫文件一定要包含以下內容：
- **程式碼風格問題**
- **主要相依套件**
- **執行環境**
- **已知架構問題**

針對這些內容進行詳細分析並撰寫。

---

# 執行指令

```bash
# Go 版：完整四人 AI 對局
go run .
go build .

# Python 終端機版（單人 vs 三 AI）
uv run mahjong.py

# Python 單人網頁版（FastAPI + WebSocket，預設 127.0.0.1:8000）
uv run --with fastapi --with "uvicorn[standard]" uvicorn web_mahjong:app --reload

# Python 多人連線版：1～4 位玩家各佔一個連接埠，空席由 AI 補位
uv run net_mahjong.py --players 2          # 席位 0 → :8001、席位 1 → :8002
uv run net_mahjong.py --seats 0 2 --ports 9000 9001
```

`.claude/settings.json` 目前只預先允許 `go build .` 與 `go run .`；執行 Python
版需另行核准 `uv run`。

---

# 專案架構

**mahjong16-go** 是以 Go 實作的 16 張手牌麻將模擬器（雙人對照傳統 13 張麻將），支援四人自動 AI 對局。

## 檔案職責

| 檔案 | 職責 |
|------|------|
| `mahjong.py` | 目前的主要實作：牌面常數、`Mahjong` / `PlayerState` / `AIContext`、胡牌與聽牌演算法、AI 出牌策略、台數計算、`main()` 終端機對局、`GameSession` 網頁狀態機 |
| `web_mahjong.py` | 單人網頁後端（FastAPI）：REST `/new_game`、`/discard`、`/action` 與 WebSocket `/ws` |
| `net_mahjong.py` | 多人連線後端：`Table` 協調器、每席一個 FastAPI app、多連接埠 uvicorn、AI 代打與離線處理 |
| `static/` | 前端：`index.html`、`app.js`（WebSocket 串流、視角旋轉）、`style.css` |
| `mahjong.go` | Go 版實作（保留參考用，與 Python 版功能不對等） |

> 註：先前版本的 `server.go` / `random.go` / `AI.go` / `client.go` 已不在 repo 中，
> Go 版目前只剩 `mahjong.go`。

## 牌面編碼

所有牌以整數 0–151 表示，每種牌面有 4 張：

```
0–35    筒（1–9 筒 × 4）
36–71   條（1–9 條 × 4）
72–107  萬（1–9 萬 × 4）
108–123 風牌（東南西北 × 4）
124–135 三元牌（中發白 × 4）
136–143 花牌（春夏秋冬梅蘭竹菊）
```

## 胡牌判定演算法

依據論文 arXiv:1707.07345 的兩個定理：

- **Theorem 1**（`isSuit`）：數值牌以貪婪遞迴分解為刻子/順子，從最小牌面開始處理。
- **Theorem 2**（`findSuitPair`）：利用 `點數 mod 3` 的餘數分組，快速定位將牌候選，縮小搜尋空間。

胡牌條件：17 張（16 張手牌 + 摸 1 張）= 1 組將牌（對子）+ 5 組面子（刻子或順子）。

## AI 出牌策略（`decidePlay`）

三階段策略（優先順序由高到低）：
1. 打出後聽牌數最多的牌
2. 若無聽牌，打出見牌數最多的牌（統計 `see[]`）
3. 隨機出牌（保底）

---

# 多人連線對戰模式（`net_mahjong.py`）

## 設計原則

**一席一埠**：第 i 位玩家連到第 i 個連接埠，該埠的 FastAPI app 在建立時就把席位
寫死，前端無法指定或偽造席位。四個埠背後共用同一個 `GameSession`。

**非玩家一律沿用既有 AI**：`GameSession(human_seats=...)` 未列入的席位，以及
離線／發呆逾時的真人席位，全部走原本的 AI 路徑（`calculate_gates()` +
`decide_play()`），不另外實作策略。

## 引擎層改動（`mahjong.py`）

| 項目 | 改動 |
|------|------|
| `GameSession(human_seats=...)` | 由單一 `HUMAN_PLAYER` 常數改為可指定 1–4 個真人席位；`_game_loop()` 內所有 `== HUMAN_PLAYER` 判斷改呼叫 `_is_human(seat)` |
| `set_seat_online(seat, online)` | 標記席位在線狀態；離線席位在**下一個決策點**自動改由 AI 操作 |
| `view(seat)` | 以任一席位視角重繪目前盤面（不推進遊戲）；輪到別家時 `phase` 為 `"waiting"` |
| `ai_suggestion()` | 回傳 AI 在目前決策點會採取的動作字串，供代打時餵給 `respond()` |
| `events(since, seat)` / `note()` | 開局以來的完整事件流（只增不減），供各連線依游標補齊漏接事件 |
| 私訊事件 | `_L(msg, private_to=seat)`：競賽模式下槓後補摸的牌面只進該席的事件流 |
| `seat_wind(seat)` | 席位 → 門風名稱 |
| `player_label(..., viewer=)` | 相對稱謂（你／下家／對家／上家）改為相對指定視角 |

`HUMAN_PLAYER` 常數保留，單人模式（`web_mahjong.py`、`main()`）行為不變。

## 並行模型（`Table`）

- 單一 driver task 推進牌局；所有 `GameSession` 的同步呼叫包在
  `asyncio.to_thread()` 並由 `Table._lock` 保護，避免與連線推播同時讀寫牌局。
- 玩家回應經 `Table.submit(seat, resp)` 餵給 driver 正在等待的 `Future`；
  席位不符會回傳錯誤而非被接受。
- 離線／發呆由 `_await_response()` 每 0.5 秒輪詢判定，逾時改呼叫
  `ai_suggestion()`，牌局不會卡在斷線的玩家身上。

## 前端（`static/app.js`）

- `zoneSeats(me)` 依本家席位旋轉四個方位，本家永遠畫在下方。
- `phase === "waiting"` 時停用手牌並顯示「等待 ○ 行動…」。
- 連線時以 `GET /seat` 與 WebSocket `hello` 取得自己的席位；單人模式 `/seat`
  回 404，前端自動退回席位 0，行為與改動前一致。

---

# 主要相依套件

- **Go 版**：僅標準函式庫（`fmt`、`math/rand`、`sort`、`bufio`、`os`、`strconv`、`strings`）。
- **Python 核心**（`mahjong.py`）：僅標準函式庫（`random`、`dataclasses`、`enum`、
  `collections.abc`、`itertools`），終端機互動另用 `readchar`。
- **Python 網頁／連線**（`web_mahjong.py`、`net_mahjong.py`）：`fastapi`、
  `uvicorn[standard]`；相依套件寫在各檔頂端的 PEP 723 `# /// script` 區塊，
  `uv run <檔案>` 會自動建立環境。

---

# 執行環境

- **Go**：1.21 以上（見 `go.mod`）。
- **Python**：3.12 以上（各腳本 `requires-python = ">=3.12"`）；語法本身相容 3.11。
- **套件管理**：[uv](https://github.com/astral-sh/uv)，靠 PEP 723 inline metadata
  解析相依，不需要 `requirements.txt` 或虛擬環境手動管理。
- **連線模式網路需求**：預設監聽 `0.0.0.0` 的 `8001`…（每位玩家 +1）；
  跨機連線需開放對應連接埠。**無任何身分驗證**，僅適合信任網路或
  SSH port forwarding／VPN。
- **瀏覽器**：需支援 WebSocket 與 Unicode 麻將符號（U+1F000–U+1F02B）。

---

# 程式碼風格問題

- 全檔以正體中文撰寫 docstring 與註解，Args／Returns／Raises 採 Google style。
- `mahjong.py` 單檔逾 3000 行，牌局規則、AI、計台、終端機 UI、網頁狀態機混在一起，
  缺乏模組邊界。
- `_game_loop()` 內以 `_rnd`、`_cl`、`_io` 等底線前綴的函式內 import 取代檔頂 import，
  且有重複 import，可整併。
- 迴圈內大量使用 `_` 前綴的臨時變數（`_pi`、`_pp`、`_t`），可讀性偏低。
- 型別註記大多齊全，但 `GameSession._gen` 宣告為 `object` 並靠 `# type: ignore`
  繞過檢查，`decide_play()` 的回傳型別也隨參數在 `int` 與 `tuple` 間切換。

---

# 已知架構問題

- `mahjong.go` 為舊版實作，與現行架構重疊，應評估是否移除
- 無任何測試檔案（`*_test.go`），核心演算法缺乏自動驗證
- `Player` 型別混合了玩家狀態、牌統計與 AI 資料，職責過多
- 遊戲主迴圈緊耦合於 `main()`，難以抽離測試
- 牌面編碼使用魔術數字（如 `3*9`、`4*4`），缺乏常數定義
- `GameSession._game_loop()` 是單一超長 generator，胡／槓／碰／吃分支層層巢狀，
  新增規則時容易改錯分支
- 連線模式一個行程只主持一副牌（單一 `Table`），無法多桌並行
- 連線模式無身分驗證與斷線續盤：行程重啟牌局即消失，任何能連上埠的人都能操作該席
- `Table` 與 `GameSession` 的狀態一致性靠單一 `asyncio.Lock` 維持，
  若日後把 driver 拆成多個 task 需重新檢視
