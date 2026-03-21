# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright",
# ]
# ///
"""偵錯 WebSocket - 使用 page.evaluate 確認 JS 狀態，並嘗試更長等待"""
from __future__ import annotations
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://localhost:8000"

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        console_msgs = []
        page.on('console', lambda msg: console_msgs.append(f'[{msg.type}] {msg.text}'))

        # 監聽網路請求
        network_reqs = []
        page.on('request', lambda req: network_reqs.append(f'{req.method} {req.url}'))
        page.on('response', lambda res: network_reqs.append(f'  -> {res.status} {res.url}'))

        print('載入頁面...')
        page.goto(BASE, timeout=15000, wait_until='networkidle')
        time.sleep(1)

        # 確認 WS 連線是否建立（透過 JS 評估）
        ws_state = page.evaluate("""() => {
            return {
                wsExists: typeof window._ws !== 'undefined',
                wsReadyState: window._ws ? window._ws.readyState : -1,
                // readyState: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
            };
        }""")
        print(f'WS 狀態（點擊前）: {ws_state}')

        # 點擊開始
        page.click('#btn-start')
        print('已點擊，等待 WS 回應...')

        # 等待最多 12 秒讓 WS 推送
        deadline = time.time() + 12
        last_count = 0
        while time.time() < deadline:
            count = page.locator('#bottom-hand button').count()
            if count != last_count:
                print(f'  bottom-hand buttons: {count}')
                last_count = count
            if count > 0:
                print('  -> 手牌已渲染！')
                break
            time.sleep(0.3)
        else:
            print('  -> 12 秒後仍未渲染')

        # JS 評估
        ws_state_after = page.evaluate("""() => {
            return {
                wsExists: typeof window._ws !== 'undefined',
                wsReadyState: window._ws ? window._ws.readyState : -1,
                waiting: typeof window._waiting !== 'undefined' ? window._waiting : null,
                statePhase: window._state ? window._state.phase : null,
                yourHandLen: window._state ? (window._state.your_hand || []).length : null,
            };
        }""")
        print(f'\nJS 狀態（點擊後）: {ws_state_after}')

        # DOM 查詢
        bottom_count = page.locator('#bottom-hand button').count()
        top_count = page.locator('#top-hand .tile').count()
        left_count = page.locator('#left-hand .tile').count()
        right_count = page.locator('#right-hand .tile').count()
        deck = page.locator('#deck-count').inner_text()
        wind_game = page.locator('#wind-game').inner_text()
        wind_round = page.locator('#wind-round').inner_text()
        bottom_html_sample = page.locator('#bottom-hand').inner_html()

        print(f'\n--- DOM 最終狀態 ---')
        print(f'#bottom-hand buttons: {bottom_count}')
        print(f'#top-hand .tile: {top_count}')
        print(f'#left-hand .tile: {left_count}')
        print(f'#right-hand .tile: {right_count}')
        print(f'#deck-count: {deck}')
        print(f'#wind-game: {wind_game}')
        print(f'#wind-round: {wind_round}')
        print(f'#bottom-hand HTML (前200): {bottom_html_sample[:200]}')

        print(f'\n--- Console ({len(console_msgs)}) ---')
        for m in console_msgs[-15:]:
            print(f'  {m}')

        print(f'\n--- Network ---')
        for r in network_reqs:
            print(f'  {r}')

        page.screenshot(path='/Users/gershwin/Downloads/llm/mahjong16/debug_ws2.png')
        print('\n截圖：debug_ws2.png')
        browser.close()

if __name__ == '__main__':
    main()
