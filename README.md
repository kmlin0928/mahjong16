# mahjong16

以 **Go**（`mahjong.go`）與 **Python**（`mahjong.py`）雙語言實作的**十六張麻將**模擬器，支援四人自動 AI 對局。

## 功能

- 完整牌組（144 張）：筒、索、萬、風牌（東南西北）、三元牌（中發白）、花牌（春夏秋冬梅蘭竹菊）
- 四人自動對局，輪流摸牌、打牌
- 自動補花（摸到花牌後補抽一張）
- 聽牌計算：列出打出每張牌後可等待的胡牌
- 胡牌判定：支援標準麻將胡牌型（眼＋順子／刻子）
- 簡易 AI：優先打出能使聽牌數最多的牌

---

## 執行方式

### Go 版本

需安裝 [Go](https://go.dev/)（1.21 以上）：

```bash
go run .      # 執行（全 AI 自動對局）
go build .    # 編譯為執行檔
```

### Python 版本

需安裝 [uv](https://github.com/astral-sh/uv)：

```bash
uv run mahjong.py   # 執行（含單元驗收測試 + 完整對局）
```

---

## 兩版本結構比較

### 1. 前端（輸出介面）

| 項目 | Go（`mahjong.go`） | Python（`mahjong.py`） |
|------|-------------------|----------------------|
| 輸出方式 | `fmt.Printf` 直接格式化 | `print()` 搭配 f-string |
| 聽牌數格式 | 浮點數（`%f`） | 整數（`int`） |
| 測試輸出 | 無內建驗收測試 | `__main__` 區塊含分層單元驗收 |
| 牌號轉換 | `nToChinese()` 為 `Mahjong` 的方法 | `n_to_chinese()` 為模組層級純函式 |
| 魔術數字 | 大量內嵌（`3*9*4`、`4*4`、`3*4+8`） | 全部以具名常數取代（`SUITED_END`、`BONUS_START` 等） |

**輸出格式範例（兩版相同）：**

```
0 1筒 3筒 ... （開局手牌及補花）

0摸 5索 打後聽牌: 2萬=3 東=1
0打 5索_ 1筒 3筒 5筒 ...
1摸 中補 ...
2胡 1筒 3筒 5筒 ...
```

---

### 2. 後端（資料結構）

| 項目 | Go（`mahjong.go`） | Python（`mahjong.py`） |
|------|-------------------|----------------------|
| 遊戲狀態型別 | `Mahjong` struct | `Mahjong` dataclass |
| 玩家容器 | `[4]Player`（固定大小陣列） | `list[PlayerState]`（動態列表） |
| 手牌容器 | `[17]int`（固定陣列，含摸入槽） | `list[int]`（動態，長度隨摸打增減） |
| 見牌統計 | `see [3*9+4+3]int`（混合在 Player） | `seen: list[int]`（在 `PlayerState`） |
| AI 決策資料 | `cPlay`、`gates` 混合在 `Player` | 獨立 `AIContext` dataclass（職責分離） |
| 牌堆操作 | `deal1()` 直接修改 slice | `deal_one()` 回傳值，remain 重新賦值 |
| 補花邏輯 | `iShowBonus()` 就地修改 `hand[i]` | `_draw_bonus()` 就地修改 `hand[idx]` |

**Go 版型別關係：**

```
Mahjong
├── nHand   int
├── remain  []int
├── sea     []int
└── players [4]Player   ← Player 混合狀態與 AI 資料
    ├── hand  [17]int
    ├── table []int
    ├── see   [27+7]int
    ├── cPlay map[int]int
    └── gates map[int]int
```

**Python 版型別關係（職責分離）：**

```
Mahjong
├── n_hand   int
├── remain   list[int]
├── sea      list[int]
├── players  list[PlayerState]   ← 純遊戲狀態
│   ├── hand  list[int]
│   ├── table list[int]
│   └── seen  list[int]
└── ai       list[AIContext]     ← 純 AI 資料
    ├── gates     dict[int, int]
    └── play_freq dict[int, int]
```

---

### 3. AI 出牌策略

兩版均採三階段優先策略，邏輯相同，但介面設計有差異：

| 項目 | Go | Python |
|------|-----|--------|
| 計算聽牌 | `gates(p)` 為 `Mahjong` 方法，回傳 `map[int]int`，**key 為牌面種類 × 4**（tile number） | `calculate_gates(m, p, ai)` 為獨立函式，結果直接寫入 `ai`，**key 為手牌索引** |
| 決定出牌 | `decidePlay(p)` 為 `Mahjong` 方法，比對 gate key 與手牌牌面 | `decide_play(p, ai)` 為獨立純函式，直接從 `ai.gates` 取索引 |
| 出牌機率欄位名稱 | `cPlay`（未出牌多 = 值小） | `play_freq`（已見多 = 值小，意義反轉） |
| 打牌交換方式 | `play(n, hand)` swap `hand[n]` ↔ `hand[hand]` | 直接 `hand[discard_idx] = hand[-1]` + `pop()` |

**Go 版三階段策略：**

1. **聽牌優先**：打出後聽牌候選數最多的牌
2. **見牌優先**：無聽牌時，打出已出現張數最多的牌（最難再摸到）
3. **隨機保底**：前兩者皆無結果時隨機選牌

**Python 版三階段策略（`decide_play`，含 DangerLevel 棄牌）：**

1. **聽牌優先**：打出後聽牌候選數最多的牌（同 Go 版）
2. **DangerLevel 最小**：無聽牌時，依放槍危險等級選最安全的牌棄出
   - 湊牌中的牌（`EXTREMELY_DANGEROUS`）視為最不應棄出（等級最高）
   - 同等級優先棄**字牌**（字牌對對手威脅最小）
   - 無字牌則棄**離中間牌最遠**的數牌（5筒/5索/5萬為中心，距離越遠越邊緣）
3. **向下相容**：`players` 未傳入時退回見牌數邏輯

> **拆牌**：當所有可棄牌均為湊牌（`EXTREMELY_DANGEROUS`），AI 被迫棄出湊牌中的牌，稱為「拆牌」。此時打牌訊息後會顯示「（拆牌）」標注。

**吃牌機制（`can_chi`，僅 Python 版，目前自動吃）：**

棄出數牌後，下一家若手牌中有兩張可與該牌合成順子的牌，則自動吃牌：

| 吃法 | 條件 | 順子組成 |
|------|------|---------|
| 後吃 | rank ≥ 2，手牌含 (k-2), (k-1) | (k-2, k-1, k) |
| 夾吃 | 1 ≤ rank ≤ 7，手牌含 (k-1), (k+1) | (k-1, k, k+1) |
| 前吃 | rank ≤ 6，手牌含 (k+1), (k+2) | (k, k+1, k+2) |

吃牌流程：
1. 從手牌移除 2 張，連同棄牌（共 3 張）移至 `table`（桌面）
2. `chi_count += 1`，棄牌從海底移除（已被吃走）
3. 吃牌方跳過摸牌（`skip_draw=True`），直接棄一張牌
4. 胡牌判定改用 `is_win_ext(hand, extra, chi_count)`，計入桌面已成面子數

> 字牌與花牌不可吃。未來可新增 `chi_ai` 決策函式，實作「可吃可不吃」策略。

**聽牌候選計算方式（`gates` / `calculate_gates`）：**

1. 統計手牌（含摸入，吃牌後手牌較少）各牌面出現次數
2. 對每個花色做前綴累加，使有出現的整個花色內所有點數都成為候選
3. 篩選「候選且尚有未見副本（< 4 張）」的牌面
4. 逐一模擬「打出第 i 張 + 摸入每個候選」，呼叫胡牌判定，統計胡牌數

**放槍危險等級（`classify_danger`，僅 Python 版）：**

| 等級 | 名稱 | 判定條件 |
|------|------|---------|
| 0 | 極度安全（絕張） | 數牌或字牌，四張全已棄出（不可能放槍），或曾被吃/碰/槓 |
| 1 | 很安全 | 花牌，或全局棄牌中同牌面出現 ≥ 2 次 |
| 2 | 安全 | 字牌（風/三元），或最近 3 輪（12 筆）內有人打出過 |
| 3 | 危險 | 數牌，曾出現在早期棄牌（12 筆以前），但最近 3 輪未出現 |
| 4 | 很危險 | 數牌，從未出現在任何人的棄牌中 |
| 5 | 極度危險（湊牌中） | 數牌順子（`find_hand_chows`）、數牌刻子/槓子（`find_hand_pungs`，≥3張）、字牌對子（`find_hand_pairs`，≥2張），不應棄出 |

> 花牌每種只有 1 張，無法達到極度安全（最高為很安全）。
> 預留 `chi_tiles`、`pon_tiles`、`kong_tiles` 參數，未來支援吃/碰/槓後可進一步細化等級。

---

### 4. 聽牌與胡牌演算法

參考論文：*Mathematical aspects of the combinatorial game "Mahjong"*（Cheng, Li & Li, arXiv:1707.07345）

#### 胡牌條件

十六張麻將：**17 張牌 = 1 對眼 + 5 組面子**（刻子或順子）

| 規則 | 含摸入總張 | 面子數 | 眼 |
|------|-----------|-------|----|
| 標準十三張 | 14 | 4 組 | 1 對 |
| 台灣十六張 | 17 | 5 組 | 1 對 |

#### `isWin` / `is_win` 整體流程

```
排序 17 張手牌
    │
    ▼
findPair / find_pair  ──→  suited[]（數牌分佈）
（Theorem 2）            honor[]（字牌分佈）
                         pair_indices（候選眼位置）
    │
    ▼  對每個候選眼
扣除眼（-2）
    │
    ├─→ isHonor / is_honor   字牌全為 0 或 3？
    │
    └─→ isSuit / is_suit     數牌可分解為面子？（Theorem 1）
            │
            └─→ 兩者皆 True → 胡牌
```

#### Theorem 1：數牌合法性（`isSuit` / `is_suit`）

> 從最小點數依序掃描：
> - 張數 ≥ 3 → 消刻子（扣 3）後**遞迴重掃**
> - 張數 1–2 → 嘗試消順子（扣連續三張各 1）後**遞迴重掃**
> - 任一位置為負數 / 無法消順子 → 立即回傳 False

此貪婪遞迴策略保證正確性，無需枚舉所有拆牌方式。

| 項目 | Go | Python |
|------|-----|--------|
| 函式簽名 | `isSuit(suited [3*9]int) bool`（傳值複製） | `is_suit(suited: list[int]) -> bool`（手動 `s = suited[:]` 複製） |
| 遞迴方式 | 直接 `return m.isSuit(suited)` | 直接 `return is_suit(s)` |
| 邊界判斷 | `i > t*9+9-3` | `offset + 2 >= TILES_PER_SUIT` |

#### Theorem 2：快速定位眼（`findSuitPair` / `_find_suit_pairs`）

將同一花色的牌依**點數 mod 3** 分成三組（餘 0、1、2）：

- **刻子**對三組計數各 +3，不影響 mod 3 差值
- **順子**對三組各 +1，差值仍不變
- **眼**（+2）使**某一組的 mod 3 餘數**與其他兩組產生差異

因此：三組中「mod 3 餘數與另外兩組不同的那組」即為眼所在組，只需在該組內枚舉候選，大幅縮小搜尋範圍。

| 項目 | Go | Python |
|------|-----|--------|
| 函式 | `findSuitPair(pad, s, pairs)` 方法，直接 append 到 `*[]int` | `_find_suit_pairs(s)` 純函式，回傳候選索引列表 |
| 字牌眼 | `findHonorPair` 遍歷所有字牌位置 | `find_pair` 最後段直接遍歷字牌區間 |
| 重複眼過濾 | `findiPair`：`s[i-1]/4 == s[i]/4` 則跳過 | `_find_i_pair`：同條件跳過 |

#### 字牌合法性（`isHonor` / `is_honor`）

去掉眼之後，字牌只能以刻子形式存在，對 7 種字牌（東南西北、中發白）逐一檢查：每種剩餘數量必須為 **0 或 3**。

---

## 牌號編碼

兩版本使用完全相同的編碼規則（0–143）：

| 範圍 | 牌種 | Go 常數 | Python 常數 |
|------|------|---------|------------|
| 0 – 107 | 筒／索／萬（各 36 張） | `3*9*4`（魔術數字） | `SUITED_END = 108` |
| 108 – 123 | 東南西北（各 4 張） | `4*4+3*9*4`（魔術數字） | `WIND_END = 124` |
| 124 – 135 | 中發白（各 4 張） | `3*4+4*4+3*9*4`（魔術數字） | `DRAGON_END = 136` |
| 136 – 143 | 花牌（各 1 張） | 隱含計算 | `BONUS_START = 136` |

---

## 限制與注意事項

- 純自動對局，不支援手動輸入（Go 版可將 `playAI` 改為 `playManual`）
- 不支援吃、碰、槓
- 不計算番數或積分
- 每次執行結果隨機
