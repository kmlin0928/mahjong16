# 初始座次隨機分配（連莊期間穩定）

## 任務清單

- [v] Task 1：GameSession 支援 seat_winds 參數並於新局隨機抽定
  - Commit 1159032：feat(session): GameSession 支援 seat_winds 參數，新局隨機抽定座次
  - 檔案：mahjong.py（GameSession.__init__、_game_loop）
  - 摘要：新增 seat_winds: list[str] | None 參數；
    為 None 時 random.shuffle 抽定，非 None 時沿用；
    回傳值 GameState 已含 seat_winds，不需額外改動

- [v] Task 2：Web handler 傳遞 seat_winds 供連莊使用
  - Commit a132aa7：feat(web): ws handler 解析 seat_winds 並傳入 GameSession
  - 檔案：web_mahjong.py（ws_game handler）
  - 摘要：new_game 命令加入 seat_winds 欄位；
    連莊/下一局時前端送回上局 seat_winds，
    handler 解析後傳入 GameSession(seat_winds=...)

- [v] Task 3：前端連莊/下一局攜帶 seat_winds
  - Commit 0c510de：feat(ui): 連莊/下一局攜帶 seat_winds 回傳後端
  - 檔案：static/app.js（_startNewGame、showGameOver）
  - 摘要：_startNewGame 新增 seatWinds 參數（預設 null）；
    連莊與下一局按鈕傳入 state.seat_winds；
    重置新局傳 null（觸發後端重新抽定）

- [v] Task 4：終端機模式新局隨機抽定並跨連莊延續
  - Commit 330658b：feat(terminal): main() 支援 seat_winds_override，新局隨機抽定座次
  - 檔案：mahjong.py（main() 函式與 __main__ 連莊迴圈）
  - 摘要：main() 新增 seat_winds_override 參數；
    fresh start (None) 時 random.sample 抽定，
    連莊迴圈回傳並帶入下一局

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- 首局開始時，四家門風隨機（非必然 東=你）
- 連莊/下一局時，座次（門風標籤）不變
- 重置新局後重新抽定
- GameState.seat_winds 正確反映本局分配
