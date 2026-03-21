# 連莊加台功能實作

## 任務清單

- [v] Task 1：確認 game_wind 永遠等於莊家門風
  - Commit 8f21b11：refactor: 莊家門風即圈風，移除獨立 game_wind 追蹤
  - 檔案：mahjong.py（_game_loop、main）、app.js（showGameOver）
  - 摘要：移除 game_wind 獨立追蹤，改為直接以 seat_winds[dealer_idx] 決定 game_wind；確保連莊/下莊邏輯一致

- [v] Task 2：修正拉莊台數公式
  - Commit 3a99d01：fix(score): 拉莊台數改為 consecutive * 2
  - 檔案：mahjong.py（score_hand）
  - 摘要：將 `("拉莊", consecutive)` 改為 `("拉莊", consecutive * 2)`
  - 驗收：連莊0→莊家1台、連莊1→莊家1+拉莊2=3台、連莊2→莊家1+拉莊4=5台

- [/] Task 3：__main__ 驗收測試
  - 檔案：mahjong.py（__main__）
  - 摘要：新增 score_hand 拉莊台數的直接測試案例，驗收三種連莊次數

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- `uv run mahjong.py` 執行無誤，拉莊測試通過
- 終端機版連莊後台數正確（連一=3台、連二=5台）
- 網頁版 gameover 畫面台數顯示正確
