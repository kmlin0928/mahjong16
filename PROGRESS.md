# PROGRESS.md

任務：將全局海底（sea）改為每位玩家各自的棄牌紀錄，為 AI 放槍預防演算法預留介面
目標檔案：mahjong.py

狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 重構棄牌資料結構：sea → discards
- **檔案範圍**：`mahjong.py`（`PlayerState` 類別、`Mahjong` 類別）
- **摘要**：在 `PlayerState` 新增 `discards: list[int]`，記錄該玩家打出的所有牌；
  `Mahjong.sea` 改為聚合屬性（或移除），統一從各玩家 `discards` 取得
- **驗收**：`PlayerState` 有 `discards` 欄位且初始為空列表
- Commit `2511efc`：refactor(mahjong-py): 新增 PlayerState.discards 個人棄牌紀錄

### 2. [/] 更新遊戲主迴圈的棄牌寫入
- **檔案範圍**：`mahjong.py`（`main()` 函式）
- **摘要**：打牌時由 `m.sea.append(tile)` 改為 `p.discards.append(tile)`，
  移除或保留 `m.sea` 作為可選的完整紀錄（供顯示或演算法使用）
- **驗收**：一局跑完後，四位玩家 `discards` 長度之和等於總打出牌數

### 3. [ ] 新增 AI 放槍預防的資料查詢介面
- **檔案範圍**：`mahjong.py`（新增獨立函式）
- **摘要**：新增 `get_dangerous_tiles(players, target_idx)` 函式，
  從其他三家的 `discards` 統計各牌面的出現頻率，
  回傳 `dict[int, int]`（牌面種類 → 出現次數），供未來 AI 決策使用
- **驗收**：對固定 `discards` 輸入呼叫後，回傳正確的統計字典；加入驗收測試

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
