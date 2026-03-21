# 花牌/手牌視覺優化 & 補花 log 改進

## 任務清單

- [v] Task 1：花牌大小與淺綠底色
  - Commit ac2bdbc：style(ui): 花牌列與面牌同大、淺綠底色
  - 檔案：static/style.css（.bonus-row .tile.discard 規則）
  - 摘要：.bonus-row 內花牌覆蓋 discard 尺寸（32×46px，與面牌同大）
    並覆蓋粉紅色改為淺綠底色（#d4f0d4）

- [v] Task 2：新摸手牌淡紫底色
  - Commit 976c62f：feat(ui): 新摸手牌淡紫底色高亮顯示
  - 檔案：mahjong.py（GameState 新增 drawn_tile_idx；_game_loop 追蹤摸牌位置）
            static/style.css（.tile-btn.drawn 淡紫樣式）
            static/app.js（renderHandButtons 設定 drawn class）
  - 摘要：摸牌後在 GameState 記錄排序後的索引；前端對應按鈕加淡紫背景；
    吃/碰/槓後無新摸牌則 drawn_tile_idx=None（不高亮）

- [v] Task 3：補花 log 加玩家身份 & 只顯示一次
  - Commit cb38f89：feat(log): 補花 log 加玩家身份並整合顯示
  - 檔案：mahjong.py（_draw_bonus_silent 與 _game_loop 初始補花邏輯）
  - 摘要：移除 _draw_bonus_silent 內的 log；
    初始補花改為每玩家結束後一次性記錄（如「東補花 梅 菊」）；
    遊戲中補花加玩家稱謂（如「南補花 春」）

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- 花牌區圖示與面牌等大、底色淺綠
- 摸牌後有淡紫色高亮，棄牌後下輪恢復
- 初始補花每人只出現一條 log，格式含玩家名
- 遊戲中補花格式同（如「北補花 冬」）
