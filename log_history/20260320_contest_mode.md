# PROGRESS.md

任務：競賽模式 — 隱藏 AI 摸牌與手牌
目標檔案：mahjong.py
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 詢問競賽模式並傳入 main()

- **檔案範圍**：`mahjong.py`（`__main__` 連莊迴圈前 + `main()` 簽名）
- **摘要**：
  - `__main__` 在連莊迴圈前詢問：「是否隱藏 AI 手牌？(y/n)」
  - `main()` 新增 `contest_mode: bool = False` 參數，連莊迴圈傳入
- **驗收**：選 y 時 contest_mode=True 傳入 main()
- **d3b67a0** feat(mahjong-py): 新增競賽模式詢問並傳入 main()

### 2. [v] 隱藏 AI 初始手牌（show_bonus 階段）

- **檔案範圍**：`mahjong.py`（`m.show_bonus()` 呼叫改為內聯迴圈）
- **摘要**：
  - 以自訂迴圈取代 `m.show_bonus()` 呼叫
  - contest_mode + AI 玩家時，以 `redirect_stdout(io.StringIO())` 壓制輸出
  - 仍執行 `_draw_bonus` 與 `add_seen` 的邏輯（保留副作用）
- **驗收**：contest_mode=True 時，AI 的初始手牌不顯示
- **0066704** feat(mahjong-py): 競賽模式隱藏 AI 初始手牌（show_bonus 階段）

### 3. [v] 隱藏 AI 摸牌名稱、剩餘手牌、胡牌手牌

- **檔案範圍**：`mahjong.py`（`main()` 主迴圈中 4 處 print 位置）
- **摘要**：
  - 摸牌行：`player != HUMAN_PLAYER and contest_mode` → 僅顯示「N摸」不顯示牌名
  - 棄牌後手牌：AI 的 `for t in p.hand` 迴圈用 `if not contest_mode` 包覆
  - AI 胡牌手牌：同上，用條件包覆
- **驗收**：contest_mode=True 時，AI 摸牌名稱、剩餘手牌、胡牌手牌均不顯示
- **8fc596d** feat(mahjong-py): 競賽模式隱藏 AI 摸牌名稱、剩餘手牌、胡牌手牌

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
