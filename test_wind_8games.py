# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
#   "fastapi",
#   "uvicorn[standard]",
# ]
# ///
"""Playwright 驗收：驗證網頁版左上角「x風y局」在 8 局中正確推進（非隨機）。

規則：
  - 新局開始固定為「東風」+「東局」
  - 連莊：圈風與局數不變
  - 下莊（下一局）：局數前進；dealer 回 0 時圈風進一檔
  - 重置新局：恢復「東風」+「東局」

預期 8 局（假設每局均為下一局）：
  東風東 → 東風南 → 東風西 → 東風北 → 南風東 → 南風南 → 南風西 → 南風北
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

PORT  = 18901
BASE  = f"http://127.0.0.1:{PORT}"
WINDS = ["東", "南", "西", "北"]
MAX_TURNS_PER_GAME = 400


def kill_port(port: int) -> None:
    """終止佔用指定 port 的殘留 process。"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
        )
        for pid_str in result.stdout.strip().split():
            try:
                os.kill(int(pid_str), signal.SIGTERM)
            except ProcessLookupError:
                pass
        if result.stdout.strip():
            time.sleep(0.5)
    except Exception:
        pass


def start_server() -> subprocess.Popen:
    kill_port(PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_mahjong:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "error"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1)
            return proc
        except Exception:
            time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("Server 啟動逾時")


def play_one_game(page) -> None:
    """自動打完一局（自動出牌、跳過所有提示），直到 gameover-banner 出現。"""
    for _ in range(MAX_TURNS_PER_GAME):
        try:
            page.wait_for_selector(
                "#gameover-banner:not([style*='display: none'])",
                timeout=6000,
            )
            return  # 遊戲結束
        except PWTimeout:
            pass

        # 提示卡可見 → 跳過
        prompt = page.locator("#prompt-card:not(.hidden)")
        if prompt.count() > 0:
            skip = page.locator("#prompt-buttons button:last-child")
            if skip.count() > 0:
                skip.first.click()
                time.sleep(0.1)
                continue

        # 出牌
        btn = page.locator("#bottom-hand .tile-btn:not([disabled])")
        if btn.count() > 0:
            btn.first.click()
            time.sleep(0.1)
        else:
            time.sleep(0.2)
    raise RuntimeError("超過步數上限仍未結束")


def get_badge(page) -> tuple[str, str]:
    """回傳 (wind_game_text, wind_round_text)，例如 ('東風', '東局')。"""
    wg = page.locator("#wind-game").inner_text(timeout=5000)
    wr = page.locator("#wind-round").inner_text(timeout=5000)
    return wg, wr


def wait_badge(page, expected_wg: str, expected_wr: str) -> None:
    """等待徽章出現期望的圈風與局數文字。"""
    page.wait_for_function(
        f"document.getElementById('wind-game').textContent === {repr(expected_wg)} && "
        f"document.getElementById('wind-round').textContent === {repr(expected_wr)}",
        timeout=30000,
    )


def main() -> None:
    proc = start_server()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(BASE, timeout=10000)
            page.click("#btn-start")

            # 追蹤預期的 (game_wind, dealer_index)
            exp_wind   = "東"
            exp_dealer = 0   # index into WINDS

            for game_num in range(1, 9):
                # 等徽章顯示期望的圈風與局數（即可確認新局 render 完成）
                expected_wg = exp_wind + "風"
                expected_wr = WINDS[exp_dealer] + "局"
                wait_badge(page, expected_wg, expected_wr)
                wg, wr = get_badge(page)
                print(f"✓ 局{game_num}：{wg} / {wr}")

                # 打完這局
                play_one_game(page)

                # 最後一局不需要點按鈕
                if game_num == 8:
                    break

                # 根據出現的按鈕決定下一局預期狀態
                lian = page.locator("#gameover-btns button:has-text('連莊')")
                xia  = page.locator("#gameover-btns button:has-text('下一局')")

                if lian.count() > 0:
                    lian.first.click()
                    # 連莊：dealer 與 game_wind 不變
                else:
                    xia.first.click()
                    # 下一局：dealer 前進
                    exp_dealer = (exp_dealer + 1) % 4
                    if exp_dealer == 0:
                        exp_wind = WINDS[(WINDS.index(exp_wind) + 1) % 4]

                time.sleep(0.2)

            page.screenshot(path=str(Path(__file__).parent / "screenshot_wind_8games.png"))
            print("\n✓ 8 局 x風y局 驗收全部通過")
            browser.close()
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
