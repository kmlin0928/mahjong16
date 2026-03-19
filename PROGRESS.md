# PROGRESS.md

任務：加入吃牌機制 — 下一家自動吃上家數牌構成順子，移至桌面後棄牌
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 新增 `can_chi` — 找出手牌中可與棄牌構成順子的第一個配對

- **檔案範圍**：`mahjong.py`（AI 放槍預防輔助函式區塊附近）
- **摘要**：
  - 輸入 `hand: list[int]`、`tile: int`（數牌）
  - 找出三種吃法（前吃/夾吃/後吃），回傳第一個可用配對 `tuple[int, int] | None`
  - 每個 tuple 為手牌中實際牌號的兩張牌；無法吃則回傳 None
- **驗收**：前吃/夾吃/後吃三情境均正確，無法吃回傳 None
- `d4ed167` feat(mahjong-py): 新增 can_chi 偵測手牌可吃棄牌的順子配對

### 2. [v] 新增 `chi_count` 至 `PlayerState`，新增 `is_win_ext`

- **檔案範圍**：`mahjong.py`（`PlayerState` dataclass；`is_win` 正下方）
- **摘要**：
  - `PlayerState` 新增 `chi_count: int = 0`，記錄已吃的面子數
  - 新增 `is_win_ext(hand, extra, meld_count)` — 計入桌面已成面子後的胡牌判定
    （hand + extra = (5 - meld_count) 面子 + 1 將牌）
- **驗收**：`is_win_ext(hand13, extra, 1)` 在正確情境下回傳 True
- `0657f70` feat(mahjong-py): 新增 chi_count 欄位與 is_win_ext 胡牌判定

### 3. [v] 更新主迴圈 — 棄牌後自動吃牌，支援吃牌後直接棄牌

- **檔案範圍**：`mahjong.py`（`main()` 函式）
- **摘要**：
  - 新增 `skip_draw: bool = False` 旗標，吃牌後下一輪跳過摸牌
  - 棄牌後：若 `discard_tile < SUITED_END`，呼叫 `can_chi` 判斷下一家是否可吃
  - 可吃時自動吃：移除手牌中的 2 張，3 張（2 手牌 + 棄牌）加入 `next_p.table`；`next_p.chi_count += 1`
  - 棄牌不計入 `discards`（已被吃走），其他玩家仍記牌
  - `player = next_player_idx`，`skip_draw = True`
  - Win check：`chi_count > 0` 的玩家改用 `is_win_ext`
  - 顯示：`N吃 X（A B）` 標注
- **驗收**：遊戲執行時偶有「吃」標注，手牌數正確
- `bfbb670` feat(mahjong-py): 主迴圈加入自動吃牌機制

### 4. [ ] README 更新吃牌機制說明

- **檔案範圍**：`README.md`
- **摘要**：
  - AI 策略區塊補充「自動吃牌」說明、`can_chi` 介紹、桌面面子記錄方式
  - 說明未來擴充：chi_ai 決策函式（目前固定自動吃）
- **驗收**：README 清楚描述吃牌流程

### 5. [ ] `__main__` 驗收測試：`can_chi` 與 `is_win_ext`

- **檔案範圍**：`mahjong.py`（`__main__` 測試區塊末尾）
- **摘要**：
  - `can_chi`：前吃/夾吃/後吃三種情境；無法吃的情境
  - `is_win_ext`：1 吃後正確胡牌、0 吃與 `is_win` 結果一致
- **驗收**：所有 assert 通過

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
