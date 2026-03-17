# PROGRESS.md

任務：將 mahjong.go 改寫成 Python 語言，過程必須重構
目標檔案：mahjong.py（新建）

狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] 建立牌面常數與編碼函式
- **檔案範圍**：`mahjong.py`（新建，僅此區段）
- **摘要**：用具名常數取代魔術數字（如 `SUIT_COUNT = 3*9*4`），並實作 `n_to_chinese(n)` 函式
- **驗收**：可呼叫 `n_to_chinese(0)` 回傳 `"1筒"`，`n_to_chinese(136)` 回傳 `"春"`
- Commit `4f77eca`：feat(mahjong-py): 新增 Python 重構任務規劃與牌面常數模組

### 2. [v] 重構資料結構（Player / Mahjong 類別拆分）
- **檔案範圍**：`mahjong.py`
- **摘要**：原版 `Player` 混合遊戲狀態與 AI 資料，拆成 `PlayerState`（手牌/花牌/見牌統計）與 `AIContext`（聽牌/出牌機率），`Mahjong` 僅保留遊戲狀態
- **驗收**：兩個類別可各自初始化且欄位名稱語意明確
- Commit `f2e67c4`：refactor(mahjong-py): 拆分 Player 為 PlayerState 與 AIContext 資料類別

### 3. [/] 實作發牌與花牌補牌邏輯
- **檔案範圍**：`mahjong.py`
- **摘要**：`deal_one()`、`init_deal()`、`show_bonus()`、`_draw_bonus()` 對應原版邏輯，含隨機洗牌
- **驗收**：`init_deal()` 後每位玩家恰有 16 張非花牌

### 4. [ ] 實作胡牌判定演算法
- **檔案範圍**：`mahjong.py`
- **摘要**：對應 `is_win()`、`is_suit()`（Theorem 1）、`find_pair()`、`find_suit_pair()`（Theorem 2）、`find_honor_pair()`，加上 docstring 解釋演算法來源
- **驗收**：已知胡牌手牌輸入 `is_win()` 回傳 `True`，未胡回傳 `False`

### 5. [ ] 實作 AI 出牌策略
- **檔案範圍**：`mahjong.py`
- **摘要**：`calculate_gates()` 計算聽牌候選，`decide_play()` 三階段策略（聽牌優先 > 出現多優先 > 隨機）
- **驗收**：對固定手牌呼叫 `decide_play()` 不拋出例外

### 6. [ ] 實作主遊戲迴圈
- **檔案範圍**：`mahjong.py`
- **摘要**：`main()` 實作四人輪流摸牌、打牌、胡牌判定、和局判定，輸出中文對局紀錄
- **驗收**：`uv run mahjong.py` 可完整執行一局對局並顯示結果

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
