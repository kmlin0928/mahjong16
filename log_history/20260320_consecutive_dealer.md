# PROGRESS.md

任務：實作連莊 — 莊家胡/和局時詢問續玩，累計連莊數
目標檔案：mahjong.py
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] main() 改為回傳 (winner: int | None, dealer_idx: int)

- **檔案範圍**：`mahjong.py`（`main()` 函式簽名與所有 return 點）
- **摘要**：
  - 函式簽名改為
    `main(dealer_idx_override: int | None = None, consecutive: int = 0) -> tuple[int | None, int]`
  - 自摸胡：`return player, dealer_idx`
  - 放槍胡：`return cand_idx, dealer_idx`
  - 和局：`return None, dealer_idx`
  - 若 `dealer_idx_override` 有值，跳過局風隨機，直接以 override 當莊家
  - 連莊時，顯示標題加上「（連莊 N 次）」
- **346924b** refactor(mahjong-py): main() 改為回傳 (winner, dealer_idx)，新增 dealer_idx_override/consecutive 參數

### 2. [v] __main__ 改為連莊迴圈

- **檔案範圍**：`mahjong.py`（`if __name__ == "__main__":` 段落）
- **摘要**：
  - `main()` 呼叫改為迴圈
  - 若 `winner == dealer_idx` 或 `winner is None`（和局）：
    顯示「連莊！繼續？(y/n)」，回答 y 則 `consecutive += 1`，
    以 `dealer_idx_override=dealer_idx` 再次呼叫 `main()`
  - 其他情況（非莊家胡）：印出「下莊」並結束

- **驗收**：
  - 莊家胡牌 → 詢問繼續，y 則開新局並顯示連莊 N 次
  - 和局 → 同上
  - 非莊家胡牌 → 顯示「下莊」並結束，不繼續
- **6d32039** feat(mahjong-py): 連莊迴圈 — 莊家胡/和局詢問續玩，累計連莊次數

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
