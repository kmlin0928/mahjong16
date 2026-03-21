# 網頁版 log 訊息依事件類型著色

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：app.js 依關鍵字加掛不同 CSS class
- [v] 檔案範圍：`static/app.js`（`appendLog`）
- 摘要：移除單一 `meld-action` 判斷，改為對應關鍵字加掛專屬 class：
  `log-bonus`（補花）、`log-discard`（打）、`log-chi`（吃）、
  `log-pon`（碰）、`log-kong`（槓）

### Task 2：style.css 定義各 class 底色
- [v] 檔案範圍：`static/style.css`
- 摘要：
  - `.log-bonus`  → 綠色  `rgba(30,120,30,0.55)`
  - `.log-discard`→ 紅色  `rgba(160,30,30,0.55)`
  - `.log-chi`    → 深灰  `rgba(60,60,60,0.65)`
  - `.log-pon`    → 藍色  `rgba(30,60,160,0.55)`
  - `.log-kong`   → 靛色  `rgba(60,30,140,0.60)`

## 驗收條件
- 手測：開局玩幾輪，log 中各類訊息顯示對應底色
