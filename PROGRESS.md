# PROGRESS.md

任務：實作「小三元」「大三元」「小四喜」「大四喜」台數，並更新 README.md
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [/] score_hand() 加入小三元／大三元判斷

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - 利用 `all_non_bonus`（含明牌）建立全局 Counter
  - `dragon_base = SUITED_KINDS + WIND_KINDS`（= 31）
  - 統計三元牌（中/發/白）各種在 counter 中的數量：
    - `>= 3` 的種類數 = `dragon_pungs`
    - `== 2` 的種類數 = `dragon_pairs`
  - 若 `dragon_pungs == 3`：大三元 +8 台
  - 若 `dragon_pungs == 2 and dragon_pairs >= 1`：小三元 +4 台
- **台數依據**：小三元 +4 台；大三元 +8 台
- **驗收**：
  - 建構含中/發/白各刻子的 all_non_bonus → 出現「大三元+8」
  - 建構含中/發刻子 + 白對子的 all_non_bonus → 出現「小三元+4」

### 2. [ ] score_hand() 加入小四喜／大四喜判斷

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - 同上，利用全局 Counter
  - `wind_base = SUITED_KINDS`（= 27），風牌 kind 為 27–30
  - 統計四風（東/南/西/北）各種在 counter 中的數量：
    - `>= 3` 的種類數 = `wind_pungs`
    - `== 2` 的種類數 = `wind_pairs`
  - 若 `wind_pungs == 4`：大四喜 +13 台
  - 若 `wind_pungs == 3 and wind_pairs >= 1`：小四喜 +6 台
- **台數依據**：小四喜 +6 台；大四喜 +13 台
- **驗收**：
  - 建構含東/南/西/北各刻子的 all_non_bonus → 出現「大四喜+13」
  - 建構含東/南/西刻子 + 北對子的 all_non_bonus → 出現「小四喜+6」

### 3. [ ] README.md 胡牌台數表格新增四條規則

- **檔案範圍**：`README.md`（「## 胡牌台數」表格）
- **摘要**：在現有表格末尾補上小三元/大三元/小四喜/大四喜四列
- **驗收**：README 台數表格出現四條新規則

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
