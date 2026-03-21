# 莊家放槍多1台

## 任務清單

- [v] Task 1：score_hand 新增「莊家放槍」加台
  - Commit 2913a7d：feat(score): score_hand 新增 pao_idx 參數與莊家放槍加台
  - 檔案：mahjong.py（score_hand，line 1502 附近）
  - 摘要：非自摸（is_tsumo=False）且放槍者為莊家（pao_idx == dealer_idx）時，
    加 ("莊家放槍", 1)；需新增 pao_idx 參數（放槍者索引）

- [v] Task 2：傳入 pao_idx 至所有 score_hand 呼叫處
  - Commit 66f818b：feat(score): 所有放槍胡呼叫點傳入 pao_idx
  - 檔案：mahjong.py（_game_loop 與 main() 中全部 score_hand 呼叫）
  - 摘要：在放槍胡（ron）判定後已知放槍者索引，補上 pao_idx= 引數；
    自摸胡時 pao_idx=None（不加台）

- [v] Task 3：__main__ 驗收測試
  - Commit f893aaa：test(score): 新增莊家放槍加台驗收測試
  - 檔案：mahjong.py（__main__ RUN_TESTS 區塊）
  - 摘要：新增 score_hand 莊家放槍加台的直接測試案例（pao=莊/非莊）

## 狀態規則
[ ]:未開始　[/]:進行中　[v]:完成

## 驗收條件
- 莊家放槍→胡牌者台數多1（含「莊家放槍+1」明細）
- 非莊放槍→台數不變
- 自摸→不觸發此規則
- `uv run python -c "..."` 快速驗證通過
