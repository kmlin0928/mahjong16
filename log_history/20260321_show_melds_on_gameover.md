# 胡牌結算顯示四家面牌

## 任務清單

- [v] Task 1：showGameOver 手牌列前加入面牌區塊
  - Commit 48cbbc1：feat(ui): 遊戲結算同時顯示四家面牌
  - 檔案：static/app.js（showGameOver 的 #gameover-hands 渲染邏輯）
  - 摘要：在每家的 hand-row 左側，先以 flatMelds(state.melds[i])
    渲染面牌（與牌桌面牌樣式相同），再接手牌；
    若無面牌則省略

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- 遊戲結束後，各家門風右方依序顯示面牌（吃/碰/槓）再接手牌
- 無副露的玩家只顯示手牌（不出現空白區塊）
- 版面與現有 tile 樣式一致
