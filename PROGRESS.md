# PROGRESS.md

任務：實作 README.md 所列全部未實作台數規則
目標檔案：mahjong.py、README.md
狀態說明：[ ] 未開始 | [/] 進行中 | [v] 完成

---

## 任務清單

### 1. [v] score_hand() 加入五暗刻（+5）與字一色（+8）

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - **五暗刻**：擴充三暗刻/四暗刻段落，`concealed_pungs >= 5 and not has_meld` → +5 台
  - **字一色**：`all_non_bonus` 全為字牌（`t >= SUITED_END`），且非空 → +8 台；
    圈風/自風/三元牌台數可複合計（不排除）
- **驗收**：
  - 手牌含 5 組暗刻 → 出現「五暗刻+5」
  - 手牌全字牌 → 出現「字一色+8」
- **5d1a6df** feat(mahjong-py): 實作五暗刻（+5）與字一色（+8）台數

### 2. [v] 傳入 is_last_tile 旗標，實作河底撈魚（+1）與海底撈月（+1）

- **檔案範圍**：`mahjong.py`（`score_hand()` 簽名、`main()` 摸牌/放槍段落）
- **摘要**：
  - `score_hand()` 新增 `is_last_tile: bool = False` 參數
  - `is_last_tile and is_tsumo` → 海底撈月 +1 台
  - `is_last_tile and not is_tsumo` → 河底撈魚 +1 台
  - 在 `main()` 中，摸最後一張牌時（`m.remain == 0` 在摸牌後）設旗標傳入
  - 放槍胡時若牌堆已空（剛摸完最後一張後他家放槍），同樣傳 `is_last_tile=True`
- **驗收**：
  - 摸最後一張牌自摸胡 → 出現「海底撈月+1」
  - 他家打出牌堆最後一張被胡 → 出現「河底撈魚+1」
- **cdf9316** feat(mahjong-py): 實作海底撈月（+1）與河底撈魚（+1）台數

### 3. [v] score_hand() 加入平胡（+2）

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - 條件：ron（`not is_tsumo`）+ 無字花（`not has_honor and len(p.bonus)==0`）+
    全順子（`p.chi_count==0` 且 `all_non_bonus` 無刻子，即每牌面種類出現次數 ≠ 3）+
    兩面聽（`wait_kinds >= 2`）
  - 全順子判斷：`counts_hand` 中所有種類的出現次數均不為 3（無三張同種暗刻）
  - "釣將不算"：`wait_kinds==1` 時不算（此條件已由 `wait_kinds>=2` 排除）
- **驗收**：
  - 五順子＋對子，ron，無字花，兩面聽 → 出現「平胡+2」
  - 同牌型但自摸胡 → 不出現平胡
- **784c152** feat(mahjong-py): 實作平胡（+2）台數

### 4. [v] score_hand() 加入全求（+2）

- **檔案範圍**：`mahjong.py`（`score_hand()` 手型台數區塊）
- **摘要**：
  - 條件：`not is_tsumo`（放槍胡）+ `len(p.hand) == 1`（閉門只剩 1 張）
  - `len(p.hand)==1` 表示所有 5 組面子均已副露，唯一閉門牌即為等牌
  - 觸發時同時應計入現行的「半求 +1」（兩者定義不衝突，可疊加）
- **驗收**：
  - 5 組副露後閉門剩 1 張，放槍胡 → 出現「全求+2」
  - 自摸版本（半求）→ 不出現全求
- **99c0407** feat(mahjong-py): 實作全求（+2）台數

### 5. [ ] main() 追蹤首巡旗標，實作天胡/人胡/地胡（各 +16）

- **檔案範圍**：`mahjong.py`（`main()` 初始化段落、`score_hand()` 簽名及規則）
- **摘要**：
  - `main()` 新增 `first_round: bool = True` 旗標；
    任何吃/碰/明槓發生後設 `first_round = False`；
    每位玩家完成第一次摸打循環後設 `first_round = False`
  - **天胡**：`first_round and is_tsumo and player == dealer_idx and not has_meld`；
    且此次摸牌為莊家補花後的第一次判胡（即原本 `skip_draw=True` 的首輪）
    → 清 16 台，不計門清/不求
  - **地胡**：`first_round and is_tsumo and player != dealer_idx and not has_meld`
    → 清 16 台，不計自摸/門清/不求
  - **人胡**：`first_round and not is_tsumo and not has_meld`（含所有玩家首巡）
    → 清 16 台，不計門清
  - 三者均在 `score_hand()` 以 `result = [...]` 過濾掉不計的項目，再 append 16 台
  - `score_hand()` 新增 `is_first_round: bool = False` 參數
- **驗收**：
  - 莊家補花後首巡自摸胡（未打任何牌）→ 出現「天胡+16」，不出現不求/門清
  - 閒家首巡第一次摸牌即自摸胡 → 出現「地胡+16」
  - 首巡他家放槍且無副露 → 出現「人胡+16」

### 6. [ ] main() 實作天聽（+8）與地聽（+4）旗標並傳入 score_hand()

- **檔案範圍**：`mahjong.py`（`main()` 初始發牌補花後段落、`score_hand()` 簽名）
- **摘要**：
  - `score_hand()` 新增 `is_tenhou: bool = False`（天聽旗標）參數
  - 天聽（+8）：初始 16 張補花完成後，立即對莊家/閒家手牌呼叫 `calculate_gates`；
    若 `ai.gates` 非空（已聽），對應玩家設 `tenhou[player] = True`；
    `tenhou_type[player] = "天聽"`（+8）
  - 地聽（+4）：無人吃碰槓的情況下，玩家首次棄牌後若仍聽牌
    (`calculate_gates` 結果非空)，設 `tenhou[player] = True`，
    `tenhou_type[player] = "地聽"`（+4）
  - 任何吃/碰/明槓後，相關玩家的天/地聽旗標失效
  - 胡牌時將 `is_tenhou` 旗標傳入 `score_hand()`
- **驗收**：
  - 手動設計聽牌初始手，補花後就聽 → 出現「天聽+8」
  - 第一次打牌後就聽且最終胡牌 → 出現「地聽+4」

### 7. [ ] README.md 將已實作規則從「尚未實作」列表中移除

- **檔案範圍**：`README.md`（「### 尚未實作規則」表格）
- **摘要**：隨各任務完成逐步移除對應列；本任務在所有前序任務完成後執行
- **驗收**：「尚未實作規則」表格清空或僅剩真正未實作項目

---

## 狀態更新規則
- [ ] 未開始
- [/] 進行中
- [v] 完成（完成後附 Commit 編號前7碼與訊息摘要）
