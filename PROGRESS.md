# PROGRESS.md

任務：實作「明槓」機制 — 棄牌後另外三家若手牌持有同牌面刻子（3 張），
      則可以槓牌，移 3 張手牌至桌面並正常摸牌打牌；優先於碰，AI 預設不自動明槓
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 新增 `can_kong` — 判斷手牌是否可明槓棄牌

- **檔案範圍**：`mahjong.py`（`can_pon` 正下方）
- **摘要**：
  - 輸入 `hand: list[int]`、`tile: int`
  - 在 hand 中找出三張同牌面種類的牌（`kind = tile // COPIES`）
  - 找到回傳 `tuple[int, int, int]`，找不到回傳 `None`
  - 數牌與字牌均可明槓；花牌（`tile >= BONUS_START`）不可槓
- **驗收**：數牌可槓/字牌可槓/只有 2 張不可槓/花牌不可槓
- `44d3313` feat(mahjong-py): 新增 can_kong 偵測手牌可明槓棄牌的槓子配對

### 2. [v] 新增 `kong_count` 至 `PlayerState`，更新 `is_win_ext`

- **檔案範圍**：`mahjong.py`（`PlayerState` dataclass；`is_win_ext`）
- **摘要**：
  - `PlayerState` 新增 `kong_count: int = 0`（`pon_count` 正下方）
  - `is_win_ext` 呼叫改為 `chi_count + pon_count + kong_count`（在主迴圈呼叫端修改）
  - 新增模組層級常數 `AI_AUTO_KONG: bool = False`，控制 AI 是否自動明槓
- **驗收**：`PlayerState` 建立後 `kong_count == 0`；`AI_AUTO_KONG` 預設 `False`
- `ea649d6` feat(mahjong-py): 新增 kong_count 欄位與 AI_AUTO_KONG 常數

### 3. [v] 更新主迴圈 — 棄牌後明槓優先於碰，槓後正常摸牌

- **檔案範圍**：`mahjong.py`（`main()` 函式，現有碰牌判斷邏輯之前）
- **摘要**：
  - 棄牌後，若 `AI_AUTO_KONG` 為 True，先掃描其他三家（依序 next, next+1, next+2）是否可槓
  - 可槓時：移除 3 張手牌，4 張加入 `kong_p.table`；`kong_p.kong_count += 1`
  - 棄牌不計入 `discards`（已被槓走），其他玩家仍記牌
  - `player = kong_idx`，**不設 `skip_draw = True`**（槓後正常摸牌打牌）
  - 找到槓牌後略過碰牌與吃牌判斷
  - win check 呼叫端改為 `p.chi_count + p.pon_count + p.kong_count`
  - 顯示：`N槓 X（A B C）` 標注
- **驗收**：`AI_AUTO_KONG = True` 時遊戲出現「槓」標注，槓後玩家手牌數正確（移除 3 張）且正常摸牌
- `d9bcbb3` feat(mahjong-py): 主迴圈加入明槓機制（AI_AUTO_KONG 控制）

### 4. [v] README 更新明槓機制說明

- **檔案範圍**：`README.md`
- **摘要**：
  - 碰牌機制說明後補充明槓段落（`can_kong` 介紹、優先順序 槓>碰>吃、槓後正常摸牌）
  - 說明 `AI_AUTO_KONG` 常數及預設值；未來擴充 `kong_ai` 決策函式
- **驗收**：README 清楚描述明槓流程與 AI 控制方式
- `8f03878` docs: README 新增明槓機制說明（can_kong、AI_AUTO_KONG、優先順序）

### 5. [/] `__main__` 驗收測試：`can_kong`

- **檔案範圍**：`mahjong.py`（`__main__` 測試區塊，`can_pon` 測試正下方）
- **摘要**：
  - 數牌可槓：手牌 3 張同 kind → 回傳 3-tuple
  - 字牌可槓：手牌 3 張同字牌 → 回傳 3-tuple
  - 只有 2 張：回傳 None
  - 花牌不可槓：tile >= BONUS_START → 回傳 None
- **驗收**：所有 assert 通過

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
