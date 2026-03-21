# 網頁版隱藏「莊家多摸 X」log

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：移除 _game_loop 的「莊家多摸」log（mahjong.py）
- [/] 檔案範圍：`mahjong.py`（`_game_loop`，lines 1971–1973）
- 摘要：刪除 `self._L(f"莊家多摸 ...")` 與 `self._L("莊家多摸（隱藏）")` 兩行

## 驗收條件
- 手測：開局後 log 不出現「莊家多摸」字樣
