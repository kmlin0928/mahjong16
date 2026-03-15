# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# 文件撰寫規則

用正體中文撰寫相關文件，回應都使用正體中文。

撰寫文件一定要包含以下內容：
- **程式碼風格問題**
- **主要相依套件**
- **執行環境**
- **已知架構問題**

針對這些內容進行詳細分析並撰寫。

---

# 執行指令

```bash
# 執行完整四人 AI 對局
go run .

# 編譯
go build .

# 若要手動出牌，將 client.go 中 main() 的 playAI(s) 改為 playManual(s)
```

允許執行的指令限定為 `go build .` 與 `go run .`（見 `.claude/settings.json`）。

---

# 專案架構

**mahjong16-go** 是以 Go 實作的 16 張手牌麻將模擬器（雙人對照傳統 13 張麻將），支援四人自動 AI 對局。

## 檔案職責

| 檔案 | 職責 |
|------|------|
| `server.go` | `Server` 型別（遊戲狀態）；`nToChinese()` 牌面編碼轉中文 |
| `random.go` | 洗牌、初始發牌、花牌補牌（`showBonus` / `iShowBonus`） |
| `AI.go` | 核心 AI：`decidePlay()`（出牌策略）、`gates()`（聽牌計算）、`isWin()`（胡牌判定）、`isSuit()`、`findPair()` |
| `client.go` | `Player` 型別；`main()` 遊戲主迴圈（四人 AI 輪流） |
| `mahjong.go` | 舊版實作（保留參考用，未被 `main()` 呼叫） |

## 牌面編碼

所有牌以整數 0–151 表示，每種牌面有 4 張：

```
0–35    筒（1–9 筒 × 4）
36–71   條（1–9 條 × 4）
72–107  萬（1–9 萬 × 4）
108–123 風牌（東南西北 × 4）
124–135 三元牌（中發白 × 4）
136–143 花牌（春夏秋冬梅蘭竹菊）
```

## 胡牌判定演算法

依據論文 arXiv:1707.07345 的兩個定理：

- **Theorem 1**（`isSuit`）：數值牌以貪婪遞迴分解為刻子/順子，從最小牌面開始處理。
- **Theorem 2**（`findSuitPair`）：利用 `點數 mod 3` 的餘數分組，快速定位將牌候選，縮小搜尋空間。

胡牌條件：17 張（16 張手牌 + 摸 1 張）= 1 組將牌（對子）+ 5 組面子（刻子或順子）。

## AI 出牌策略（`decidePlay`）

三階段策略（優先順序由高到低）：
1. 打出後聽牌數最多的牌
2. 若無聽牌，打出見牌數最多的牌（統計 `see[]`）
3. 隨機出牌（保底）

---

# 主要相依套件

僅使用 Go 標準函式庫，無外部相依：`fmt`、`math/rand`、`sort`、`bufio`、`os`、`strconv`、`strings`。

---

# 已知架構問題

- `mahjong.go` 為舊版實作，與現行架構重疊，應評估是否移除
- 無任何測試檔案（`*_test.go`），核心演算法缺乏自動驗證
- `Player` 型別混合了玩家狀態、牌統計與 AI 資料，職責過多
- 遊戲主迴圈緊耦合於 `main()`，難以抽離測試
- 牌面編碼使用魔術數字（如 `3*9`、`4*4`），缺乏常數定義
