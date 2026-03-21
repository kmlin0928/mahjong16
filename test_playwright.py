# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
#   "fastapi",
#   "uvicorn[standard]",
# ]
# ///
"""Playwright 端到端驗收：啟動 web server，用 headless 瀏覽器打完一局麻將。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PORT   = 18900
BASE   = f"http://127.0.0.1:{PORT}"
SHOT   = Path(__file__).parent / "screenshot_gameover.png"
MAX_TURNS = 400   # 安全上限，防止無窮迴圈


def start_server() -> subprocess.Popen:
    """以 subprocess 啟動 uvicorn，回傳 Popen 物件。"""
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "web_mahjong:app",
            "--host", "127.0.0.1",
            "--port", str(PORT),
            "--log-level", "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 等待 server 就緒
    import urllib.request, urllib.error
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1)
            return proc
        except Exception:
            time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("Server 啟動逾時")


def play_game(page) -> str:
    """自動打牌直到遊戲結束，回傳 winner 文字。"""
    # 點開始
    page.click("#btn-start")

    for turn in range(MAX_TURNS):
        # 等待頁面進入穩定狀態（WebSocket 推送完畢）
        try:
            # 優先等 gameover-banner 出現
            page.wait_for_selector(
                "#gameover-banner:not([style*='display: none'])",
                timeout=8000,
            )
            break  # 遊戲結束
        except PWTimeout:
            pass

        # 若提示卡片可見 → 點「跳過」
        prompt = page.locator("#prompt-card:not(.hidden)")
        if prompt.count() > 0:
            skip = page.locator("#prompt-buttons button:last-child")
            if skip.count() > 0:
                skip.first.click()
                time.sleep(0.15)
                continue

        # 出牌：點手牌第一張（若可點）
        btn = page.locator("#bottom-hand .tile-btn:not([disabled])")
        if btn.count() > 0:
            btn.first.click()
            time.sleep(0.15)
        else:
            # 等待下一個可操作狀態
            time.sleep(0.3)
    else:
        raise RuntimeError(f"超過 {MAX_TURNS} 步仍未結束")

    # 取得勝者文字
    title = page.locator("#gameover-title").inner_text()
    return title


def main() -> None:
    proc = start_server()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page(viewport={"width": 1024, "height": 768})
            page.goto(BASE, timeout=10000)

            winner_text = play_game(page)

            # 截圖留存
            page.screenshot(path=str(SHOT))
            print(f"截圖已存：{SHOT}")
            print(f"遊戲結束：{winner_text!r}")

            assert winner_text, "gameover-title 不應為空"
            print("✓ 一局完整驗收通過")
            browser.close()
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
