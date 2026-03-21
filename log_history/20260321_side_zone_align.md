# 左右玩家區塊往上偏移

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：style.css — 左右區塊改為靠上對齊並加 padding-top
- [v] 檔案範圍：`static/style.css`
- Commit 893745e：fix(style): 左右側玩家區塊靠上對齊，避免棄牌行被截斷
- 摘要：
  新增 `#zone-left, #zone-right` 的 CSS 覆寫：
  `justify-content: flex-start; padding-top: 8%;`
  讓上家/下家的手牌與棄牌從頂部起排，避免棄牌行被截斷

## 驗收條件
- 網頁開局後，左側（上家）與右側（下家）的棄牌行可見
- 版面無明顯失衡
