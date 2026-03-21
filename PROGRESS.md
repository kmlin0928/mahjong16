# 圈風獨立 + 順時針座次 + 64 組合測試

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：mahjong.py — GameState/GameSession 新增 game_round_wind + 順時針座次
- [/] 檔案範圍：`mahjong.py`（GameState、GameSession.__init__、_game_loop）
- 摘要：
  1. GameState 新增 `game_round_wind: str = ""` 欄位（圈風，與 game_wind 局風分離）
  2. GameSession.__init__ 新增 `game_round_wind: str | None = None` 參數
  3. seat_winds 改為順時針旋轉：`[_SEAT_WIND_NAMES[(offset+i)%4] for i in range(4)]`
  4. _game_loop 顯示改為「東風南局」格式
  5. _snapshot 填入 state.game_round_wind

### Task 2：mahjong.py — main() 與 __main__ 連莊迴圈
- [ ] 檔案範圍：`mahjong.py`（main()、__main__ 迴圈）
- 摘要：
  1. main() 新增 `game_round_wind` 參數
  2. 顯示格式同 Task 1
  3. __main__ 迴圈：下莊時推進莊家，圈風在 4 局後循環

### Task 3：app.js + web_mahjong.py — 前端圈風顯示
- [ ] 檔案範圍：`static/app.js`, `web_mahjong.py`
- 摘要：
  1. wind-game 改顯示 state.game_round_wind + "風"
  2. wind-round 顯示莊家門風 + "局"
  3. 連莊/下一局按鈕傳遞 game_round_wind
  4. web_mahjong.py ws 接收 game_round_wind 並傳給 GameSession

### Task 4：mahjong.py — 64 組合整合測試
- [ ] 檔案範圍：`mahjong.py`（__main__ 測試區塊）
- 摘要：新增測試：對 4(圈風)×4(莊家位)×4(人類門風) = 64 組合各跑 GameSession，
  驗證開局無例外、game_round_wind/game_wind/seat_winds 正確

## 驗收條件
- 網頁風圈徽章顯示「東風」+「南局」（若圈風東、莊家南）
- 終端機顯示「【你是 西｜東風南局】莊家：南」格式
- 64 組合測試全部通過
