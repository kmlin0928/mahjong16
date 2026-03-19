# PROGRESS.md

任務：實作牌面危險等級分類（4 級），為 AI 放槍預防提供評分基礎
目標檔案：mahjong.py

狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 定義 DangerLevel 列舉與等級說明
- **檔案範圍**：`mahjong.py`（新增常數區段）
- **摘要**：以 `IntEnum` 定義四個等級常數：
  `VERY_SAFE=1`、`SAFE=2`、`DANGEROUS=3`、`VERY_DANGEROUS=4`，
  並附上完整 docstring 說明各等級的判定條件
- **驗收**：可直接比較 `DangerLevel.VERY_SAFE < DangerLevel.DANGEROUS`
- Commit `9179001`：feat(mahjong-py): 新增 DangerLevel 危險等級列舉

### 2. [/] 實作 classify_danger() 核心分類函式
- **檔案範圍**：`mahjong.py`（AI 放槍預防輔助函式區段）
- **摘要**：`classify_danger(tile, players, target_idx, round_num)` 依序判斷：
  1. **很安全**：花牌（>= BONUS_START），或全局棄牌中出現 ≥ 2 次
  2. **安全**：字牌（wind/dragon），或最近 3 輪（12 次棄牌）內有人打出過
  3. **危險**：數牌，且曾出現在早期棄牌（第 3 輪之前），但最近 3 輪未出現
  4. **很危險**：數牌，從未出現在任何人的棄牌中
  （吃/碰/槓預留為參數，目前以空列表傳入）
- **驗收**：對花牌回傳 VERY_SAFE；對字牌回傳 SAFE；
  對從未出現的數牌回傳 VERY_DANGEROUS；對曾早期出現的數牌回傳 DANGEROUS

### 3. [ ] 加入驗收測試並更新 README 危險等級說明
- **檔案範圍**：`mahjong.py`（驗收區段）、`README.md`
- **摘要**：在 `__main__` 驗收區塊加入 classify_danger() 的四種等級測試；
  在 README 的「AI 出牌策略」章節補充危險等級表格
- **驗收**：`uv run mahjong.py` 全部通過，README 有危險等級說明

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
