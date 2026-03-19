# PROGRESS.md

任務：實作「碰牌」機制 — 棄牌後另外三家若可與棄牌組成刻子則自動碰牌，
      優先於下家吃牌，碰牌方移至桌面後棄牌
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [/] 新增 `can_pon` — 判斷手牌是否可碰棄牌

- **檔案範圍**：`mahjong.py`（`can_chi` 正下方，AI 放槍預防輔助函式區塊）
- **摘要**：
  - 輸入 `hand: list[int]`、`tile: int`（任意牌）
  - 在 hand 中找出兩張同牌面種類（`kind = tile // COPIES`）的牌
  - 找到回傳 `tuple[int, int]`，找不到回傳 `None`
  - 數牌與字牌均可碰，花牌不可碰（`tile >= BONUS_START` 回傳 None）
- **驗收**：數牌可碰/字牌可碰/牌不夠不可碰/花牌不可碰

### 2. [ ] 新增 `pon_count` 至 `PlayerState`

- **檔案範圍**：`mahjong.py`（`PlayerState` dataclass，`chi_count` 正下方）
- **摘要**：
  - `PlayerState` 新增 `pon_count: int = 0`，記錄已碰的面子數
  - 更新 `is_win_ext` docstring：`meld_count` 同時計入吃與碰的面子數
- **驗收**：`PlayerState` 建立後 `pon_count == 0`

### 3. [ ] 更新主迴圈 — 棄牌後優先碰牌，碰牌後直接棄牌

- **檔案範圍**：`mahjong.py`（`main()` 函式，現有 chi 判斷邏輯附近）
- **摘要**：
  - 棄牌後先掃描其他三家（依序 next, next+1, next+2）是否可碰
  - 可碰時：移除手牌中的 2 張，3 張加入 `pon_p.table`；`pon_p.pon_count += 1`
  - 棄牌不計入 `discards`（已被碰走），其他玩家仍記牌
  - `player = pon_player_idx`，`skip_draw = True`
  - 碰牌優先：找到碰牌後略過吃牌判斷
  - Win check：`pon_count > 0` 的玩家已有 `chi_count`，改用 `is_win_ext(hand, extra, chi_count + pon_count)`
  - 顯示：`N碰 X（A B）` 標注
- **驗收**：遊戲執行時偶有「碰」標注，碰牌方手牌數正確，碰後直接棄牌

### 4. [ ] README 更新碰牌機制說明

- **檔案範圍**：`README.md`
- **摘要**：
  - 吃牌機制表格後補充碰牌說明（`can_pon` 介紹、優先順序、字牌可碰）
  - 說明未來擴充：`pon_ai` 決策函式（目前固定自動碰）
- **驗收**：README 清楚描述碰牌流程與優先順序

### 5. [ ] `__main__` 驗收測試：`can_pon`

- **檔案範圍**：`mahjong.py`（`__main__` 測試區塊，`can_chi` 測試正下方）
- **摘要**：
  - 數牌可碰：手牌有 2 張同花色同點數
  - 字牌可碰：手牌有 2 張同字牌
  - 牌不夠：手牌只有 1 張 → 回傳 None
  - 花牌不可碰：tile >= BONUS_START → 回傳 None
- **驗收**：所有 assert 通過

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
