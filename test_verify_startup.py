# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
# ]
# ///
"""
驗收測試：連接已在執行中的 http://localhost:8000
確認首頁載入、開局按鈕、四方位手牌區、風圈徽章。
"""
from __future__ import annotations

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://localhost:8000"
SHOT_DIR = Path(__file__).parent


def run_tests() -> None:
    results: list[dict] = []

    def record(step: str, passed: bool, detail: str = "") -> None:
        status = "PASS" if passed else "FAIL"
        results.append({"step": step, "status": status, "detail": detail})
        icon = "✓" if passed else "✗"
        print(f"  {icon} [{status}] {step}" + (f": {detail}" if detail else ""))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_default_timeout(10000)

        # ── 步驟 1：開啟首頁，確認頁面正常載入 ──────────────────────
        print("\n[步驟 1] 開啟首頁")
        try:
            resp = page.goto(BASE, timeout=10000, wait_until="domcontentloaded")
            status_code = resp.status if resp else None
            title = page.title()
            record("HTTP 狀態碼", status_code == 200, f"HTTP {status_code}")
            record("頁面標題", bool(title), f"title='{title}'")
            # 確認關鍵 DOM 元素存在
            overlay_visible = page.locator("#start-overlay").is_visible()
            record("開始 overlay 顯示", overlay_visible)
            wind_game_text = page.locator("#wind-game").inner_text()
            wind_round_text = page.locator("#wind-round").inner_text()
            record("風圈 #wind-game 有文字（初始）", bool(wind_game_text.strip()), f"'{wind_game_text}'")
            record("風圈 #wind-round 有文字（初始）", bool(wind_round_text.strip()), f"'{wind_round_text}'")
        except Exception as e:
            record("首頁載入", False, str(e))
            browser.close()
            _print_summary(results)
            return

        page.screenshot(path=str(SHOT_DIR / "shot_01_homepage.png"))
        print("    截圖已存：shot_01_homepage.png")

        # ── 步驟 2：點擊「開始對局」按鈕 ────────────────────────────
        print("\n[步驟 2] 點擊「開始對局」按鈕")
        try:
            btn_start = page.locator("#btn-start")
            btn_visible = btn_start.is_visible()
            record("按鈕 #btn-start 存在且可見", btn_visible,
                   f"按鈕文字='{btn_start.inner_text()}'")
            if btn_visible:
                btn_start.click()
                # 等待 overlay 消失（代表遊戲開始）
                page.wait_for_selector("#start-overlay[style*='display: none']",
                                       timeout=5000)
                record("點擊後 overlay 隱藏", True)
        except PWTimeout:
            # overlay 可能用 class 隱藏而非 inline style，再試一次
            try:
                overlay_hidden = not page.locator("#start-overlay").is_visible()
                record("點擊後 overlay 隱藏（第二次確認）", overlay_hidden)
            except Exception as e2:
                record("點擊後 overlay 隱藏", False, str(e2))
        except Exception as e:
            record("點擊「開始對局」", False, str(e))

        # ── 步驟 3：等待遊戲狀態推送（WebSocket） ───────────────────
        print("\n[步驟 3] 等待 WebSocket 推送遊戲狀態")
        try:
            # 等待 #bottom-hand 內出現至少一個 button（表示手牌已渲染）
            page.wait_for_selector("#bottom-hand button", timeout=8000)
            record("WebSocket 狀態推送完成", True, "bottom-hand 已有 button")
        except PWTimeout:
            record("WebSocket 狀態推送完成", False, "等待 8 秒後 bottom-hand 仍無 button")

        page.screenshot(path=str(SHOT_DIR / "shot_02_after_start.png"))
        print("    截圖已存：shot_02_after_start.png")

        # ── 步驟 4：驗證四個方位的手牌區 ────────────────────────────
        print("\n[步驟 4] 驗證四方位手牌區")

        # 4a. #bottom-hand（你的手牌，應有 16 張 button）
        bottom_btns = page.locator("#bottom-hand button")
        bottom_count = bottom_btns.count()
        record("#bottom-hand 有手牌按鈕", bottom_count > 0, f"共 {bottom_count} 個 button")
        record("#bottom-hand 有 16 張牌", bottom_count == 16, f"實際 {bottom_count} 張")

        # 4b. #top-hand（對家手牌，競賽模式為背面牌 div.tile.back）
        top_tiles = page.locator("#top-hand .tile")
        top_count = top_tiles.count()
        record("#top-hand 有元素", top_count > 0, f"共 {top_count} 個 .tile 元素")

        # 4c. #left-hand（上家手牌）
        left_tiles = page.locator("#left-hand .tile")
        left_count = left_tiles.count()
        record("#left-hand 有元素", left_count > 0, f"共 {left_count} 個 .tile 元素")

        # 4d. #right-hand（下家手牌）
        right_tiles = page.locator("#right-hand .tile")
        right_count = right_tiles.count()
        record("#right-hand 有元素", right_count > 0, f"共 {right_count} 個 .tile 元素")

        # ── 步驟 5：確認風圈徽章顯示風向文字 ──────────────────────
        print("\n[步驟 5] 確認風圈徽章")
        wind_game = page.locator("#wind-game").inner_text()
        wind_round = page.locator("#wind-round").inner_text()
        record("#wind-game 顯示圈風", bool(wind_game.strip()) and wind_game != "?風",
               f"內容='{wind_game}'")
        record("#wind-round 顯示局風", bool(wind_round.strip()) and wind_round != "?局",
               f"內容='{wind_round}'")

        # ── 步驟 6：額外資訊確認 ────────────────────────────────────
        print("\n[步驟 6] 額外資訊")
        deck_count = page.locator("#deck-count").inner_text()
        record("牌堆剩餘張數顯示", "剩" in deck_count and "—" not in deck_count,
               f"'{deck_count}'")

        # 截圖記錄最終開局狀態
        page.screenshot(path=str(SHOT_DIR / "shot_03_game_state.png"))
        print("    截圖已存：shot_03_game_state.png")

        browser.close()

    _print_summary(results)


def _print_summary(results: list[dict]) -> None:
    passed = sum(1 for r in results if r["status"] == "PASS")
    total  = len(results)
    failed = total - passed

    print("\n" + "=" * 60)
    print("測試結果摘要")
    print("=" * 60)
    print(f"  通過：{passed} / {total}")
    if failed:
        print(f"  失敗：{failed} 項")
        print("\n  失敗清單：")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    - {r['step']}: {r['detail']}")
    else:
        print("  所有測試項目通過！")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
