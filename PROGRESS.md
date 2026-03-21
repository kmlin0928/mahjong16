# 拉莊台數規則修正

## 狀態規則
[ ] 未開始  [/] 進行中  [v] 完成

## 任務清單

### Task 1：mahjong.py — score_hand 拉莊公式依情況計算
- [/] 檔案範圍：`mahjong.py`（score_hand，約 line 1506）
- 摘要：
  將原本一律 consecutive×2 改為：
  1. winner == dealer_idx：拉莊 = consecutive × 2（不變）
  2. winner != dealer_idx AND (is_tsumo OR pao_idx == dealer_idx)：
     拉莊 = 1 + consecutive × 2
  3. winner != dealer_idx AND not is_tsumo AND pao_idx != dealer_idx：
     不加拉莊

### Task 2：mahjong.py — 更新 __main__ 拉莊驗收測試
- [ ] 檔案範圍：`mahjong.py`（__main__ 拉莊單元測試）
- 摘要：
  現有莊家自摸測試（winner=dealer）維持 consecutive×2 結果；
  新增非莊家自摸情境：consecutive=1→3，consecutive=2→5；
  新增非莊家放槍情境：拉莊=0

## 驗收條件
- 莊家勝 consecutive=2：拉莊=4（不變）
- 非莊家自摸 consecutive=2：拉莊=5
- 非莊家放槍 consecutive=2：拉莊=0
- __main__ 測試全部通過
