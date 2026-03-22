# 胡牌顯示放槍者或自摸

## 任務清單

### Task 1：mahjong.py — 網頁版 _game_loop 補齊放槍牌名
- [/] 檔案範圍：`mahjong.py`（_game_loop，line ~2217）
- 摘要：
  ron 訊息從 `XX胡！（YY 放槍）`
  改為 `XX胡 牌！（YY 放槍）`，加入胡牌的牌名

### Task 2：mahjong.py — 網頁版 _game_loop 補齊搶槓胡資訊
- [ ] 檔案範圍：`mahjong.py`（_game_loop，line ~2117）
- 摘要：
  搶槓胡訊息從 `XX搶槓胡！`
  改為 `XX搶槓胡 牌！（YY 加槓）`，加入牌名與加槓者

## 驗收條件
- 網頁版 log-box 中：放槍胡顯示胡的那張牌與放槍者名稱
- 搶槓胡顯示被搶的那張牌與加槓者名稱
- 自摸胡維持不變（已正確）
