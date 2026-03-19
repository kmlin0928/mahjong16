# PROGRESS.md

任務：改變 AI 棄牌邏輯 — 以 DangerLevel 分類後棄最安全牌，極度危險時為「拆牌」
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 新增 `_get_meld_kinds` — 偵測手牌中屬於湊牌的牌面種類集合

- **檔案範圍**：`mahjong.py`（`danger_discard_index` 正上方）
- **摘要**：
  - 輸入 17 張牌號 `hand17`，建立 suited[] 與 honor[] 計數陣列
  - 呼叫 `find_hand_chows` / `find_hand_pungs` / `find_hand_pairs`，收集所有湊牌牌面種類索引
  - 回傳 `set[int]`（全局牌面種類索引，含字牌偏移量）
- **驗收**：可被後續函式呼叫，結果正確區分湊牌與孤張
- `75b9cde` feat(mahjong-py): 新增 _get_meld_kinds 偵測手牌湊牌種類集合

### 2. [v] 新增 `danger_discard_index` — 按 DangerLevel 選出最佳棄牌索引

- **檔案範圍**：`mahjong.py`（`_get_meld_kinds` 正下方）
- **摘要**：
  - 輸入 `hand17: list[int]`、`players: list[PlayerState]`
  - 對每張牌：湊牌種類 → `EXTREMELY_DANGEROUS`；其餘 → `classify_danger(tile, players)`
  - 選出最小 DangerLevel；同等級優先棄字牌；無字牌則棄離 5（5筒/5索/5萬）最遠的數牌
  - 回傳 `tuple[int, DangerLevel]`（索引、選中牌的等級），供呼叫端判斷是否拆牌
- **驗收**：已知情境下選出正確索引
- `3f728d1` feat(mahjong-py): 新增 danger_discard_index 按 DangerLevel 選出棄牌

### 3. [v] 修改 `decide_play` — 整合 DangerLevel 策略，替換 Stage 2+3

- **檔案範圍**：`mahjong.py`（`decide_play` 函式）
- **摘要**：
  - 新增 `players: list[PlayerState]` 參數（預設 `None` 保持向下相容）
  - Stage 1（聽牌）保留；Stage 2+3 改為呼叫 `danger_discard_index`
  - 若 players 為 None，退回原有見牌數邏輯（向下相容）
- **驗收**：`uv run mahjong.py` 執行無誤，現有測試不受影響
- `f67b5a0` feat(mahjong-py): 修改 decide_play 整合 DangerLevel 棄牌策略

### 4. [ ] 更新主迴圈 — 傳入 players，偵測並顯示「拆牌」

- **檔案範圍**：`mahjong.py`（`main()` 中 `decide_play` 呼叫處）
- **摘要**：
  - 改為 `decide_play(p, ai, m.players)` 並取得回傳的 DangerLevel
  - 若 level == `EXTREMELY_DANGEROUS`，在打牌訊息後加上 `（拆牌）` 標注
- **驗收**：執行主遊戲時，必要時印出「拆牌」

### 5. [ ] README 新增 AI 策略說明與「拆牌」術語

- **檔案範圍**：`README.md`
- **摘要**：
  - 說明新三階段策略：聽牌 > DangerLevel 最小 > 字牌優先 > 離5最遠
  - 加入「拆牌」定義：被迫棄出 EXTREMELY_DANGEROUS 牌（湊牌）時稱為拆牌
- **驗收**：README 說明清楚，`uv run mahjong.py` 無誤

### 6. [ ] `__main__` 驗收測試：`danger_discard_index` 情境測試

- **檔案範圍**：`mahjong.py`（`__main__` 測試區塊末尾）
- **摘要**：
  - 全字牌手牌 → 選字牌棄出
  - 全數牌同等級 → 棄最遠離5的牌
  - 混合湊牌+孤張 → 棄孤張
  - 湊牌為最小等級（拆牌情境）→ level 為 EXTREMELY_DANGEROUS
- **驗收**：所有 assert 通過

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
