# 修正：非莊家方位不顯示「連莊N」

## 任務清單

[/] Task 1：補上 .dealer-badge.hidden 的隱藏規則

## 狀態規則
[ ] 未開始 | [/] 進行中 | [v] 完成

---

## Task 1：補上 .dealer-badge.hidden 的隱藏規則
**檔案範圍**: `static/style.css`
**摘要**: 目前 `.hidden` 只對 `#prompt-card.hidden` 定義了 `display: none`，
`.dealer-badge.hidden` 沒有規則，導致四個方位的連莊標籤全部顯示。
在 style.css 的 `.dealer-badge` 區塊後加上 `.dealer-badge.hidden { display: none; }`。

**驗收**: 開局後只有莊家方位出現「連莊0」金色標籤，其餘三家無任何標籤。
