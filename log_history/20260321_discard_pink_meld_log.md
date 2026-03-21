# 棄牌粉紅底 & 吃碰槓補花 log 醒目顯示

## 任務清單

- [v] Task 1：棄牌加粉紅色背景
  - Commit e494289：style(ui): 棄牌底色改為粉紅色 (#ffd6e7)
  - 檔案：static/style.css（.tile.discard 規則）
  - 摘要：在 .tile.discard 加 background: #ffd6e7（粉紅）；
    覆蓋花牌綠色背景（花牌棄牌也用粉紅）

- [v] Task 2：吃/碰/槓/補花 log 條目醒目樣式
  - Commit b087b4f：feat(ui): 吃/碰/槓/補花 log 條目醒目顯示
  - 檔案：static/style.css（新增 p.meld-action）、
    static/app.js（appendLog 偵測關鍵字加 class）
  - 摘要：appendLog 中若訊息含「吃」「碰」「槓」「補花」，
    p 元素加 meld-action class；CSS 設定大字、加底色，
    讓這些訊息在現有 log-box 中明顯突出（不新增任何 div）

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- 棄牌區底色為粉紅（瀏覽器目視確認）
- 吃/碰/槓/補花動作出現在 log 時，字體明顯大且有底色
- 普通摸牌/打牌訊息樣式不變
