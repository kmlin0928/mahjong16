# PROGRESS.md

任務：面牌顯示優化、AI seen 補記、主迴圈重構、整合測試
目標檔案：mahjong.py
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 面牌分組顯示 — 吃/碰/槓組以 `[A B C]` 標示，花牌獨立標注

- **檔案範圍**：`mahjong.py`（`main()` 打牌顯示段落；`n_to_chinese` 相關輔助）
- **摘要**：
  - 目前 `p.table` 混放花牌與吃/碰/槓牌，全部以 `|牌名` 顯示，難以辨認組別
  - 新增 `PlayerState` 欄位 `bonus: list[int]`（花牌）與 `melds: list[list[int]]`（面牌組）
    分別記錄，取代原本統一放在 `table` 的做法
  - 打牌顯示改為：手牌後先輸出花牌（`花:名稱`），再輸出各面牌組（`[A B C]`）
  - 吃/碰/槓時改將花牌放入 `bonus`、面牌組放入 `melds`
- **驗收**：遊戲輸出清楚區分花牌與面牌組，吃/碰/槓組可見括號分組
- `1ce9a98` feat(mahjong-py): 面牌分組顯示（bonus/melds 欄位取代 table）

### 2. [v] AI seen 補記 — 吃/碰/槓後將手牌移出的牌記入其他玩家 seen

- **檔案範圍**：`mahjong.py`（`main()` chi/pon/kong 執行段落）
- **摘要**：
  - 棄牌已透過 `add_seen` 通知其他玩家，但手牌中移出的配牌（ta, tb 或 ta,tb,tc）尚未記錄
  - 吃/碰/槓完成後，對其餘三家呼叫 `add_seen(ta)` / `add_seen(tb)` 等，讓 AI 知道這些牌已公開
- **驗收**：`seen` 統計包含面牌組的每張牌；DangerLevel 計算更準確
- `35483d5` feat(mahjong-py): 吃/碰/槓後補記手牌配牌至其他玩家 seen

### 3. [/] 重構主迴圈 — 抽出 `_do_chi` / `_do_pon` / `_do_kong` 輔助函式

- **檔案範圍**：`mahjong.py`（`main()` 下方新增輔助函式區塊）
- **摘要**：
  - 目前吃/碰/槓各自在 `main()` 內展開，邏輯重複（移牌、記 seen、印出標注）
  - 抽出三個輔助函式，接受 `(m, discard_player, meld_player, discard_tile, tiles)` 參數
  - `main()` 改為呼叫這三個函式，行數大幅減少
- **驗收**：`uv run mahjong.py` 執行結果與重構前相同；程式碼行數減少

### 4. [ ] 整合測試 — 固定 seed 執行一局並驗證關鍵輸出格式

- **檔案範圍**：`mahjong.py`（`__main__` 測試區塊末尾）
- **摘要**：
  - 以 `random.seed(固定值)` 執行 `main()`，捕捉 stdout
  - 驗證：輸出包含「摸」「打」「胡」或「和局」其中一個結尾字；
    若有吃/碰/槓，對應標注存在且手牌數合理
  - 採用 `io.StringIO` + `contextlib.redirect_stdout` 捕捉輸出
- **驗收**：assert 通過，測試執行時間 < 5 秒

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
