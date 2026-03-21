# 自摸胡牌顯示摸入牌

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：mahjong.py — AI 自摸胡顯示摸入牌（終端機 + 網頁）
- [v] 檔案範圍：`mahjong.py`（main() AI 自摸約 line 2478；_game_loop AI 自摸約 line 2065）
- Commit e62d7e5：fix(mahjong): 自摸胡牌顯示摸入牌（終端機與網頁 AI）
- 摘要：
  1. main() AI 自摸：`{plabel(player)}胡`
     → `{plabel(player)}自摸胡 {n_to_chinese(drawn)}`
  2. _game_loop AI 自摸：`{plabel(player)}自摸胡！`
     → `{plabel(player)}自摸胡 {n_to_chinese(drawn)}！`

## 驗收條件
- 終端機對局 AI 胡牌時，顯示「下家自摸胡 ２萬」等格式
- 網頁對局 AI 胡牌 log 顯示「下家自摸胡 ２萬！」
- 人類自摸顯示不受影響
