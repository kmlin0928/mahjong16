# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
# ]
# ///
"""偵錯 WebSocket 連線問題"""
from __future__ import annotations
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"

def main():
    console_msgs = []
    ws_msgs = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})

        page.on('console', lambda msg: console_msgs.append(f'[{msg.type}] {msg.text}'))

        def on_ws(ws):
            print(f'WS opened: {ws.url}')
            def on_recv(payload):
                if isinstance(payload, str):
                    ws_msgs.append(payload[:400])
                else:
                    ws_msgs.append(f'(binary {len(payload)} bytes)')
            ws.on('framereceived', on_recv)

        page.on('websocket', on_ws)

        page.goto(BASE, timeout=10000, wait_until='domcontentloaded')
        time.sleep(1.5)

        page.click('#btn-start')
        print('已點擊開始對局，等待 6 秒...')
        time.sleep(6)

        # 查詢元素
        bottom_count = page.locator('#bottom-hand button').count()
        top_tile = page.locator('#top-hand .tile').count()
        left_tile = page.locator('#left-hand .tile').count()
        right_tile = page.locator('#right-hand .tile').count()
        deck = page.locator('#deck-count').inner_text()
        wind_game = page.locator('#wind-game').inner_text()
        wind_round = page.locator('#wind-round').inner_text()
        overlay_vis = page.locator('#start-overlay').is_visible()
        gameover_vis = page.locator('#gameover-banner').is_visible()
        bottom_html = page.locator('#bottom-hand').inner_html()

        print(f'\n--- DOM 狀態 ---')
        print(f'start-overlay 可見: {overlay_vis}')
        print(f'gameover-banner 可見: {gameover_vis}')
        print(f'bottom-hand buttons: {bottom_count}')
        print(f'top-hand .tile: {top_tile}')
        print(f'left-hand .tile: {left_tile}')
        print(f'right-hand .tile: {right_tile}')
        print(f'deck: {deck}')
        print(f'wind-game: {wind_game}')
        print(f'wind-round: {wind_round}')
        print(f'bottom-hand innerHTML (前300): {bottom_html[:300]}')

        print(f'\n--- WS 訊息 ({len(ws_msgs)} 則) ---')
        for i, m in enumerate(ws_msgs[:8]):
            print(f'  [{i}] {m}')

        print(f'\n--- Console ({len(console_msgs)} 則) ---')
        for m in console_msgs:
            print(f'  {m}')

        page.screenshot(path='/Users/gershwin/Downloads/llm/mahjong16/debug_ws.png')
        print('\n截圖：debug_ws.png')
        browser.close()

if __name__ == '__main__':
    main()
