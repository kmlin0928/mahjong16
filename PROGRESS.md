# 右區（下家）棄牌排列修正

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：style.css — #zone-right 改為 column-reverse，棄牌排在頂部
- [/] 檔案範圍：`static/style.css`
- 摘要：
  1. 將現有 `#zone-left, #zone-right` 規則拆分：
     - `#zone-left` 保持 `justify-content: flex-start; padding-top: 8%`（不變）
     - `#zone-right` 改為 `flex-direction: column-reverse; justify-content: flex-start; padding-bottom: 8%`
  2. 效果：右區視覺順序從上到下為 棄牌→手牌→副露→補花→標籤，
     棄牌朝左靠近桌面中央，與左區形成對稱

## 驗收條件
- 右區（下家）的棄牌顯示於區塊頂部，不被截斷
- 左區（上家）佈局不受影響
