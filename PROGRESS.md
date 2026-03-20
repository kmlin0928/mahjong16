# PROGRESS.md

任務：實作「獨聽」+1 台
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [/] score_hand() 加入獨聽判斷

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - 從 `hand_all` 移除 `winning_tile`，得到胡前的手牌 `hand_for_gates`
  - 掃描全部 34 種牌面種類（`kind * COPIES`，0–33，排除花牌）：
    呼叫 `is_win_ext(hand_for_gates, kind * COPIES, meld_count)`
  - 統計能胡的種類數 `wait_kinds`
  - 若 `wait_kinds == 1`：加 `("獨聽", 1)`
- **台數依據**：獨聽（僅等一種牌）+1 台
- **驗收**：對局中僅單張等胡時，台數出現「獨聽+1」；有多種等牌時不顯示

### 2. [ ] 更新 score_hand() docstring

- **檔案範圍**：`mahjong.py`（`score_hand()` Args 說明）
- **摘要**：補充獨聽邏輯說明（掃描 34 種牌面）
- **驗收**：docstring 說明獨聽判斷條件

### 3. [ ] README.md 胡牌台數表格新增獨聽

- **檔案範圍**：`README.md`（「## 胡牌台數」表格）
- **摘要**：在表格末尾加入「獨聽 | +1 | 僅等一種牌面才能胡牌」
- **驗收**：README 表格出現獨聽一列

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
