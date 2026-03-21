# 連莊鎖定莊家防護

## 任務清單

### Task 1：mahjong.py — _game_loop 連莊時強制要求 dealer_idx_override
- [/] 檔案範圍：`mahjong.py`（_game_loop，seat_winds/dealer_idx 分配段落）
- 摘要：
  若 `self.consecutive > 0` 但 `self.dealer_idx_override is None`，
  raise RuntimeError 提醒呼叫方

### Task 2：app.js — 連莊按鈕確保傳遞 dealer_idx 與 seat_winds
- [ ] 檔案範圍：`static/app.js`（showGameOver 連莊按鈕）
- 摘要：
  將 null 檢查改為明確型別保護（`typeof dealerIdx === 'number'`）

## 驗收條件
- 呼叫 `GameSession(consecutive=1)` 而不提供 `dealer_idx_override` 時拋出 RuntimeError
- 網頁版連莊時莊家/門風維持不變
