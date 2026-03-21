# 左區（上家）不跟隨中央 log 拉伸

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：style.css — #zone-left 加 align-self: start
- [/] 檔案範圍：`static/style.css`
- 摘要：
  在 `#zone-left` 規則新增 `align-self: start`，
  使其高度由自身內容決定，不隨 #zone-center 的 log 高度拉伸

## 驗收條件
- 中央 log 增長時，左區（上家）高度不跟著增加
- 右區（下家）顯示不受影響
