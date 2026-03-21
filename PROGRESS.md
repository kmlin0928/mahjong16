# 修復風圈文字顯示與莊家連莊標示

## 任務清單

[v] Task 1：修復風圈徽章「?風?局」文字未顯示
- ca8d90a fix(web): 修正風圈徽章文字未顯示，改以雙層 div 架構取代 fixed 偽元素
[/] Task 2：莊家方位區顯示「連莊 N」標示

## 狀態規則
[ ] 未開始 | [/] 進行中 | [v] 完成

---

## Task 1：修復風圈徽章文字顯示
**檔案範圍**: `static/style.css`
**摘要**:
- `#wind-game` / `#wind-round` 顏色改為白色（原為黃/綠），確保在深色背景可見
- 修正 `::before` 偽元素造成的 z-index 覆蓋問題（改為 `position: absolute` 相對定位）
- 讓徽章外層加上 `position: relative` 使偽元素正確定位

**驗收**: 開局後左上角顯示「東風」＋「西局」（或對應圈風/莊家門風），字體清晰可見。

---

## Task 2：莊家方位區顯示「連莊 N」
**檔案範圍**: `static/index.html`, `static/style.css`, `static/app.js`
**摘要**:
- 四方位各加一個 `.dealer-badge` 隱藏元素（id: `dealer-bottom/right/top/left`）
- `renderState` 時依 `state.dealer_idx` 顯示對應方位的「連莊 N」，其餘隱藏
- N 取 `state.consecutive`，格式固定為「連莊N」（含 N=0）

**驗收**: 開局後莊家所在區域出現「連莊0」標示；連莊後顯示「連莊1」等；換莊後標示跟著移到新莊家方位。
