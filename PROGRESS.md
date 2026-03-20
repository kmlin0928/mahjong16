# PROGRESS.md

任務：實作「槓上開花」+1台 — 補花/加槓補牌後自摸胡
目標檔案：mahjong.py
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [/] 追蹤補牌旗標並傳入 score_hand()

- **檔案範圍**：`mahjong.py`（`main()` 摸牌段落、加槓段落；`score_hand()` 函式簽名）
- **摘要**：
  - 在正常摸牌前記錄原始牌號 `_orig_drawn = drawn`；
    補花後若 `_orig_drawn >= BONUS_START`（原為花牌），設旗標 `after_supplement = True`
  - 加槓後補摸那張牌，強制設 `after_supplement = True`
  - `score_hand()` 新增 `is_kong_flower: bool = False` 參數；
    若 True 則 `result.append(("槓上開花", 1))`
  - 自摸胡呼叫 `score_hand()` 時，傳入 `is_kong_flower=after_supplement`
- **驗收**：摸到花牌補牌後自摸胡，台數明細出現「槓上開花+1」

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
