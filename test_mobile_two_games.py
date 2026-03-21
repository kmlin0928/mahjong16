# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
# ]
# ///
"""
手機模式端到端測試：使用 iPhone 14 viewport（390×844），
只靠按鈕操作完成兩局麻將遊戲。
伺服器需在執行前已啟動於 http://127.0.0.1:18901。
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://127.0.0.1:18901"
MAX_TURNS = 600  # 安全上限，防止無窮迴圈
WORK_DIR = Path(__file__).parent


def play_one_game(page, game_num: int) -> str:
    """
    自動出牌直到 #gameover-banner 顯示，回傳 #gameover-title 文字。

    策略：
    - 若 #prompt-card 可見（非 hidden）→ 點最後一個 button（跳過）
    - 否則點 #bottom-hand .tile-btn:not([disabled]) 第一個（出牌）
    """
    for turn in range(MAX_TURNS):
        # 優先檢查遊戲是否已結束
        try:
            page.wait_for_selector(
                "#gameover-banner:not([style*='display: none'])",
                timeout=3000,
            )
            break  # 遊戲結束，跳出迴圈
        except PWTimeout:
            pass

        # 若提示卡片可見 → 點最後一個按鈕（跳過/不要）
        prompt_visible = page.evaluate("""
            () => {
                const el = document.querySelector('#prompt-card');
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return !el.classList.contains('hidden')
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            }
        """)

        if prompt_visible:
            buttons = page.locator("#prompt-buttons button")
            count = buttons.count()
            if count > 0:
                buttons.nth(count - 1).click()
                time.sleep(0.1)
                continue

        # 出牌：點手牌第一張可用牌
        hand_btn = page.locator("#bottom-hand .tile-btn:not([disabled])")
        if hand_btn.count() > 0:
            hand_btn.first.click()
            time.sleep(0.1)
        else:
            # 無可出牌，等待狀態更新
            time.sleep(0.25)
    else:
        page.screenshot(path=str(WORK_DIR / f"screenshot_mobile_game{game_num}_stuck.png"))
        raise RuntimeError(f"第 {game_num} 局超過 {MAX_TURNS} 步仍未結束")

    # 等待 gameover-banner 完全顯示
    page.wait_for_selector(
        "#gameover-banner:not([style*='display: none'])",
        timeout=10000,
    )
    title = page.locator("#gameover-title").inner_text()
    return title


def main() -> None:
    """主測試流程：以手機 viewport 完成兩局遊戲。"""
    with sync_playwright() as pw:
        # 使用 iPhone 14 viewport（390×844）
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page = context.new_page()

        print(f"導航至 {BASE} ...")
        page.goto(BASE, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)

        # --- 第一局 ---
        print("\n=== 第一局開始 ===")
        print("點擊「開始對局」按鈕...")
        page.click("#btn-start")
        time.sleep(0.5)

        result1 = play_one_game(page, game_num=1)

        shot1 = WORK_DIR / "screenshot_mobile_game1.png"
        page.screenshot(path=str(shot1))
        print(f"第一局結果：{result1!r}")
        print(f"截圖已存：{shot1}")

        # --- 第二局 ---
        print("\n=== 第二局開始 ===")
        print("點擊「連莊/新局」按鈕...")
        # 點 #gameover-btns 第一個按鈕（連莊 or 開始新局）
        gameover_btn = page.locator("#gameover-btns button")
        btn_count = gameover_btn.count()
        if btn_count == 0:
            raise RuntimeError("找不到 #gameover-btns button，無法開始第二局")
        gameover_btn.first.click()
        time.sleep(0.5)

        result2 = play_one_game(page, game_num=2)

        shot2 = WORK_DIR / "screenshot_mobile_game2.png"
        page.screenshot(path=str(shot2))
        print(f"第二局結果：{result2!r}")
        print(f"截圖已存：{shot2}")

        browser.close()

    # --- 最終報告 ---
    print("\n" + "=" * 50)
    print("手機操作兩局遊戲測試結果")
    print("=" * 50)
    print(f"第一局：{result1!r}")
    print(f"  截圖：{shot1}")
    print(f"第二局：{result2!r}")
    print(f"  截圖：{shot2}")
    print()
    if result1 and result2:
        print("確認：手機只靠按鈕可完成兩局遊戲。[PASS]")
    else:
        print("警告：部分局次結果為空，請確認遊戲邏輯。[FAIL]")


if __name__ == "__main__":
    main()
