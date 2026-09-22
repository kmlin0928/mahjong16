# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi",
#   "uvicorn[standard]",
#   "websockets",
# ]
# ///
"""多人連線對戰模式驗收測試。

執行方式::

    uv run test_net_mahjong.py

測試內容
--------
1. 引擎層：1～4 個真人席位都能跑完整盤，各席視角／手牌張數／提示歸屬正確。
2. 競賽模式資訊隔離：槓後補摸的牌面只進該席事件流。
3. AI 代打：席位離線後由既有 AI 演算法接手，牌局不會卡住。
4. 單人模式向下相容：``GameSession()`` 預設行為與改動前一致。
5. CLI 參數推導與驗證：``--players`` / ``--seats`` / ``--ports`` 的合法與非法組合。
6. 端到端：實際開兩個連接埠，兩個 WebSocket 玩家打完一整盤。
7. 存取控制（SEC-1／SEC-2）：席位 token 與 Origin 檢查。
8. 輸入驗證（ERR-1／ERR-2）：畸形的 ``discard`` / ``new_game`` 不會終止牌局。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import random
import sys
import urllib.error
import urllib.request

import websockets

import mahjong
import net_mahjong as nm
from mahjong import GameSession

HOST = "127.0.0.1"
PORTS = {0: 18901, 1: 18902}
TOKENS = {0: "test-token-seat0", 1: "test-token-seat1"}


def ws_url(seat: int, port: int, token: str | None = None) -> str:
    """組出帶 token 的 WebSocket 網址。"""
    tok = TOKENS[seat] if token is None else token
    return f"ws://{HOST}:{port}/ws?t={tok}"


def _play_out(session: GameSession) -> "mahjong.GameState":
    """以 ``ai_suggestion()`` 代打，把牌局一路推到結束。"""
    state = session.start()
    steps = 0
    while state.phase != "game_over":
        steps += 1
        assert steps < 5000, "牌局未收斂"
        state = session.respond(session.ai_suggestion())
    return state


# ---------------------------------------------------------------------------
# 1. 引擎層：多席位視角
# ---------------------------------------------------------------------------

def test_multi_seat_engine() -> None:
    """1～4 個真人席位的各種組合都能跑完，且每席視角自洽。"""
    for seats in ([0], [3], [0, 2], [1, 3], [0, 1, 2], [0, 1, 2, 3]):
        for seed in range(5):
            random.seed(seed)
            s = GameSession(contest=True, human_seats=seats)
            state = s.start()
            cursors = {k: 0 for k in s.human_seats}
            while state.phase != "game_over":
                actor = state.current_seat
                assert actor in s.human_seats, (actor, s.human_seats)
                assert state.your_seat == actor
                for k in s.human_seats:
                    v = s.view(k)
                    assert v.your_seat == k
                    assert v.current_seat == actor
                    assert v.phase == (state.phase if k == actor else "waiting")
                    assert len(v.your_hand) == v.hand_counts[k]
                    if k != actor:
                        assert v.prompt is None, "提示不該送給非當前席位"
                    s.events(cursors[k], k)
                    cursors[k] = v.event_index
                state = s.respond(s.ai_suggestion())
            assert state.current_seat == -1
            assert state.all_hands is not None
        print(f"  human_seats={seats}：5 盤全數跑完")


def test_invalid_human_seats() -> None:
    """human_seats 為空或超出 0–3 時應拒絕。"""
    for bad in ([], [4], [-1], [0, 9]):
        try:
            GameSession(human_seats=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"human_seats={bad} 應拋 ValueError")
    print("  非法 human_seats 均被拒絕")


# ---------------------------------------------------------------------------
# 2. 競賽模式資訊隔離
# ---------------------------------------------------------------------------

def test_private_events() -> None:
    """私訊事件只進該席事件流；競賽模式補摸牌面不外洩。"""
    s = GameSession(contest=True, human_seats=[0, 1, 2, 3])
    s.start()
    s.note("公開事件")
    s.note("只有席 2 看得到", seat=2)
    base = len(s._event_log) - 2
    assert s.events(base, 0) == ["公開事件"]
    assert s.events(base, 2) == ["公開事件", "只有席 2 看得到"]
    assert "只有席 2 看得到" not in s.view(0).log
    assert "只有席 2 看得到" in s.view(2).log

    # 補摸事件需要槓才會產生，暫時打開 AI 自動槓
    original = mahjong.AI_AUTO_KONG
    mahjong.AI_AUTO_KONG = True
    try:
        for seed in range(80):
            random.seed(seed)
            g = GameSession(contest=True, human_seats=[0, 1, 2, 3])
            _play_out(g)
            owners = {msg: pv for msg, pv in g._event_log if "補摸" in msg}
            if not owners:
                continue
            for msg, pv in owners.items():
                assert pv is not None, f"競賽模式補摸未設為私訊：{msg}"
                for k in range(4):
                    assert (msg in g.events(0, k)) == (k == pv), (msg, k, pv)
            print(f"  競賽模式補摸只有該席可見（{len(owners)} 則）")
            break
        else:
            raise AssertionError("80 盤內未出現補摸事件，無法驗證")
    finally:
        mahjong.AI_AUTO_KONG = original


# ---------------------------------------------------------------------------
# 3. AI 代打
# ---------------------------------------------------------------------------

def test_ai_takeover_engine() -> None:
    """席位標記離線後，下一個決策點即由 AI 操作。"""
    random.seed(11)
    s = GameSession(contest=True, human_seats=[0, 1, 2, 3])
    state = s.start()
    n = 0
    while state.phase != "game_over":
        n += 1
        if n == 5:
            s.set_seat_online(1, False)
            s.set_seat_online(3, False)
        elif n > 5:
            assert state.current_seat in s.online_seats, state.current_seat
        state = s.respond(s.ai_suggestion())
    assert s.online_seats == [0, 2]
    print("  離線席位由 AI 接手，牌局跑完")


# ---------------------------------------------------------------------------
# 4. 單人模式向下相容
# ---------------------------------------------------------------------------

def test_single_player_compat() -> None:
    """未指定 human_seats 時，行為與改動前的單人模式一致。"""
    random.seed(3)
    s = GameSession(contest=True)
    state = s.start()
    assert s.human_seats == [0]
    assert state.your_seat == 0
    while state.phase != "game_over":
        state = s.respond(s.ai_suggestion())
    assert state.all_hands is not None
    print("  單人模式（human_seats 預設）向下相容")


# ---------------------------------------------------------------------------
# 5. CLI 參數
# ---------------------------------------------------------------------------

def test_cli_args() -> None:
    """席位與連接埠的推導與錯誤參數檢查。"""
    p = nm.build_parser()
    assert nm.resolve_seats_ports(p.parse_args([])) == ([0], {0: 8001})
    assert nm.resolve_seats_ports(p.parse_args(["--players", "4"])) == (
        [0, 1, 2, 3], {0: 8001, 1: 8002, 2: 8003, 3: 8004})
    assert nm.resolve_seats_ports(p.parse_args(
        ["--seats", "0", "2", "--ports", "9000", "9001"])) == ([0, 2], {0: 9000, 2: 9001})
    assert nm.resolve_seats_ports(p.parse_args(
        ["--players", "2", "--base-port", "7000"])) == ([0, 1], {0: 7000, 1: 7001})
    for argv, keyword in [
        (["--players", "5"], "人數"),
        (["--players", "0"], "人數"),
        (["--seats", "0", "4"], "席位"),
        (["--seats", "0", "0"], "重複"),
        (["--players", "2", "--ports", "9000"], "數量"),
        (["--players", "2", "--ports", "9000", "9000"], "重複"),
    ]:
        try:
            nm.resolve_seats_ports(p.parse_args(argv))
        except SystemExit as exc:
            assert keyword in str(exc), (argv, str(exc))
        else:
            raise AssertionError(f"{argv} 應被拒絕")
    print("  CLI 參數推導與驗證")


# ---------------------------------------------------------------------------
# 6. 端到端：兩個連接埠、兩個 WebSocket 玩家
# ---------------------------------------------------------------------------

class _Bot:
    """極簡玩家：一律打第 0 張，只接受胡牌提示。"""

    def __init__(self, seat: int, port: int) -> None:
        self.seat, self.port = seat, port
        self.states: list[dict] = []
        self.logs: list[str] = []
        self.hello: dict | None = None
        self.moves = 0

    async def run(self, quit_after: int | None = None) -> None:
        async with websockets.connect(ws_url(self.seat, self.port)) as ws:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                kind, value = msg["t"], msg["v"]
                if kind == "hello":
                    self.hello = value
                elif kind == "log":
                    self.logs.append(value)
                elif kind == "error":
                    raise AssertionError(f"席位 {self.seat} 收到 error：{value}")
                elif kind == "state":
                    self.states.append(value)
                    assert value["your_seat"] == self.seat
                    assert len(value["your_hand"]) == value["hand_counts"][self.seat]
                    if value["phase"] == "game_over":
                        return
                    if value["phase"] == "waiting":
                        assert value["prompt"] is None
                        continue
                    self.moves += 1
                    if quit_after is not None and self.moves >= quit_after:
                        return          # 模擬中途離線
                    if value["phase"] == "human_discard":
                        await ws.send(json.dumps({"cmd": "discard", "idx": 0}))
                    else:
                        kind_ = value["prompt"]["type"]
                        act = "y" if kind_.startswith(("win", "rob")) else "n"
                        await ws.send(json.dumps({"cmd": "action", "action": act}))


async def _serve(table: nm.Table, stop: asyncio.Event) -> None:
    """在背景跑起所有席位的服務，直到 stop 被設定。"""
    servers = [
        nm._SharedSignalServer(
            nm.uvicorn.Config(nm.create_seat_app(table, seat), host=HOST,
                              port=port, log_level="error")
        )
        for seat, port in PORTS.items()
    ]
    task = asyncio.gather(*(srv.serve() for srv in servers))
    await stop.wait()
    for srv in servers:
        srv.should_exit = True
    await task
    await table.shutdown()


async def _run_table(quit_after: int | None) -> tuple[nm.Table, _Bot, _Bot]:
    """開一桌（席位 0、1 真人，2、3 AI），跑完後回傳結果。"""
    random.seed(42)
    table = nm.Table(seats=[0, 1], seat_ports=PORTS, contest=True,
                     disconnect_grace=1.0, afk_seconds=0.0, auto_start=True,
                     seat_tokens=dict(TOKENS))
    stop = asyncio.Event()
    server = asyncio.create_task(_serve(table, stop))
    for _ in range(80):                       # 等連接埠就緒
        await asyncio.sleep(0.05)
        try:
            reader, writer = await asyncio.open_connection(HOST, PORTS[0])
        except OSError:
            continue
        writer.close()
        break

    bot0, bot1 = _Bot(0, PORTS[0]), _Bot(1, PORTS[1])
    await asyncio.wait_for(
        asyncio.gather(bot0.run(), bot1.run(quit_after=quit_after)), timeout=180)
    if quit_after is not None:
        await asyncio.wait_for(table._driver, timeout=180)   # 由 AI 代打跑完
    stop.set()
    await server
    return table, bot0, bot1


async def test_end_to_end() -> None:
    """兩位真人玩家透過各自的連接埠打完一盤，並驗證離線代打。"""
    table, bot0, bot1 = await _run_table(quit_after=None)
    assert bot0.hello is not None and bot0.hello["seat"] == 0
    assert bot1.hello is not None and bot1.hello["seat"] == 1
    assert bot0.states[-1]["phase"] == "game_over"
    assert bot1.states[-1]["phase"] == "game_over"
    assert bot0.states[-1]["human_seats"] == [0, 1]
    winds = bot0.states[-1]["seat_winds"]
    leaked = [l for l in bot0.logs if "補摸" in l and not l.startswith(winds[0])]
    assert not leaked, f"競賽模式事件外洩：{leaked}"
    print(f"  兩家各自完成 {bot0.moves} / {bot1.moves} 次決策，"
          f"結果 {bot0.states[-1]['winner'] or '和局'}")

    table, _, _ = await _run_table(quit_after=3)
    assert table._driver.done()
    assert table._session is not None
    assert table._session.view(1).phase == "game_over"
    takeover = [l for l in table._session.events(0, 1) if "代打" in l]
    assert takeover, "離線後未出現 AI 代打事件"
    print(f"  離線代打：{takeover[0]}")


# ---------------------------------------------------------------------------
# 7. 存取控制（SEC-1 席位 token、SEC-2 Origin 檢查）
# ---------------------------------------------------------------------------

SEC_PORT = 18911
SEC_TOKEN = "sec-token-seat0"


@contextlib.asynccontextmanager
async def _one_seat_server(port: int, token: str, **table_kw):
    """開一個單席位的服務供存取控制測試使用，離開時關閉。"""
    table = nm.Table(seats=[0], seat_ports={0: port}, contest=True,
                     auto_start=False, seat_tokens={0: token}, **table_kw)
    srv = nm._SharedSignalServer(
        nm.uvicorn.Config(nm.create_seat_app(table, 0), host=HOST, port=port,
                          log_level="critical")
    )
    task = asyncio.create_task(srv.serve())
    for _ in range(100):                      # 等連接埠就緒
        await asyncio.sleep(0.05)
        try:
            _, writer = await asyncio.open_connection(HOST, port)
        except OSError:
            continue
        writer.close()
        break
    try:
        yield table
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await table.shutdown()


async def _ws_rejected(url: str, **kw) -> bool:
    """嘗試連線，回傳是否被伺服器拒絕握手。"""
    try:
        ws = await asyncio.wait_for(websockets.connect(url, **kw), timeout=10)
    except websockets.exceptions.InvalidStatus:
        return True                            # accept() 前關閉 → HTTP 403
    except websockets.exceptions.InvalidStatusCode:   # 舊版 websockets
        return True
    await ws.close()
    return False


def _http(port: int, path: str, cookie: str | None = None) -> tuple[int, str, str | None]:
    """發一個同步 HTTP GET，回傳 (狀態碼, 內文, Set-Cookie)。"""
    req = urllib.request.Request(f"http://{HOST}:{port}{path}")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status, resp.read().decode(), resp.headers.get("set-cookie")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), exc.headers.get("set-cookie")


async def test_seat_token() -> None:
    """SEC-1：沒有正確 token 就拿不到席位，連 HTTP 主頁都進不去。"""
    async with _one_seat_server(SEC_PORT, SEC_TOKEN):
        base = f"ws://{HOST}:{SEC_PORT}/ws"
        assert await _ws_rejected(base), "無 token 的 WebSocket 應被拒絕"
        assert await _ws_rejected(f"{base}?t=wrong"), "錯誤 token 應被拒絕"
        assert await _ws_rejected(f"{base}?t="), "空 token 應被拒絕"
        assert not await _ws_rejected(f"{base}?t={SEC_TOKEN}"), "正確 token 應被接受"

        # HTTP 端點同樣需要 token
        status, body, _ = await asyncio.to_thread(_http, SEC_PORT, "/")
        assert status == 401, f"GET / 無 token 應回 401，實得 {status}"
        status, _, cookie = await asyncio.to_thread(
            _http, SEC_PORT, f"/?t={SEC_TOKEN}")
        assert status == 200, f"GET / 帶 token 應回 200，實得 {status}"
        assert cookie is not None and "HttpOnly" in cookie, f"cookie 未設或未加 HttpOnly：{cookie}"
        assert "samesite=strict" in cookie.lower(), f"cookie 缺 SameSite=Strict：{cookie}"

        status, body, _ = await asyncio.to_thread(_http, SEC_PORT, "/seat")
        assert status == 401, f"GET /seat 無 token 應回 401，實得 {status}"
        status, body, _ = await asyncio.to_thread(
            _http, SEC_PORT, "/seat", f"{nm.seat_cookie_name(0)}={SEC_TOKEN}")
        assert status == 200 and json.loads(body)["seat"] == 0, body

        # 瀏覽器實際走的路徑：WS 不帶 query token，只帶先前存下的 cookie
        assert not await _ws_rejected(
            base, additional_headers={"Cookie": f"{nm.seat_cookie_name(0)}={SEC_TOKEN}"}
        ), "帶正確 cookie 的 WebSocket 應被接受"
    print("  無／錯 token 一律被拒；正確 token 與 cookie 皆可進入")


async def test_origin_check() -> None:
    """SEC-2：Origin 與 Host 不符的 WebSocket 握手應被拒（CSWSH）。"""
    # 先單測純函式，避免只靠端到端
    assert nm.origin_allowed(None, "127.0.0.1:8001"), "無 Origin 的非瀏覽器客戶端應放行"
    assert nm.origin_allowed("http://127.0.0.1:8001", "127.0.0.1:8001")
    assert not nm.origin_allowed("http://evil.example.com", "127.0.0.1:8001")
    assert not nm.origin_allowed("http://127.0.0.1:8002", "127.0.0.1:8001"), "別的埠算跨站"
    assert not nm.origin_allowed("null", "127.0.0.1:8001"), "sandbox iframe 的 null 應被拒"
    assert not nm.origin_allowed("javascript:alert(1)", "127.0.0.1:8001")

    async with _one_seat_server(SEC_PORT + 1, SEC_TOKEN):
        port = SEC_PORT + 1
        url = f"ws://{HOST}:{port}/ws?t={SEC_TOKEN}"
        assert await _ws_rejected(
            url, additional_headers={"Origin": "http://evil.example.com"}
        ), "惡意 Origin 即使帶對 token 也應被拒"
        assert not await _ws_rejected(
            url, additional_headers={"Origin": f"http://{HOST}:{port}"}
        ), "同源 Origin 應被接受"
    print("  跨站 Origin 被拒，同源與非瀏覽器客戶端放行")


# ---------------------------------------------------------------------------
# 8. 輸入驗證（ERR-1 discard 索引、ERR-2 new_game 參數）
# ---------------------------------------------------------------------------

def test_engine_param_validation() -> None:
    """ERR-2 第二道防線：GameSession 直接收到畸形參數時立刻拒絕。"""
    bad_kwargs = [
        ({"dealer_idx_override": 99}, "dealer_idx"),
        ({"dealer_idx_override": -1}, "dealer_idx"),
        ({"dealer_idx_override": "x"}, "dealer_idx"),
        ({"dealer_idx_override": True}, "dealer_idx"),
        ({"seat_winds": ["東"]}, "seat_winds"),
        ({"seat_winds": ["東", "東", "南", "西"]}, "seat_winds"),
        ({"seat_winds": ["東", "南", "西", "火"]}, "seat_winds"),
        ({"seat_winds": "東南西北"}, "seat_winds"),
        ({"consecutive": "abc"}, "consecutive"),
        ({"consecutive": -1}, "consecutive"),
        ({"consecutive": 10 ** 9}, "consecutive"),
        ({"game_round_wind": "火"}, "game_round_wind"),
    ]
    for kwargs, keyword in bad_kwargs:
        try:
            GameSession(**kwargs)
        except ValueError as exc:
            assert keyword in str(exc), (kwargs, str(exc))
        else:
            raise AssertionError(f"{kwargs} 應拋 ValueError")
    # 合法參數仍可正常開局
    random.seed(0)
    s = GameSession(dealer_idx_override=2, consecutive=1,
                    seat_winds=["南", "西", "北", "東"], game_round_wind="南")
    st = s.start()
    assert st.dealer_idx == 2 and st.seat_winds == ["南", "西", "北", "東"]
    print(f"  {len(bad_kwargs)} 組非法開局參數全被引擎擋下，合法組合正常開局")


def test_engine_response_validation() -> None:
    """ERR-1 第二道防線：畸形回應被拒，且 generator 不會損毀。"""
    random.seed(1)
    s = GameSession()
    state = s.start()
    while state.phase != "human_discard":
        state = s.respond(s.ai_suggestion())
    size = len(state.your_hand)
    for bad in ["abc", str(size), str(size + 100), "-1", "", "0x1", " 0", "chi:0"]:
        try:
            s.respond(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"discard {bad!r} 應被拒絕")
    # 關鍵：被拒之後 generator 仍然活著，同一位玩家可以重送
    state = s.respond("0")
    assert state.phase in ("human_discard", "prompt", "waiting", "game_over")
    while state.phase != "game_over":
        state = s.respond(s.ai_suggestion())
    assert state.all_hands is not None
    print("  畸形回應被拒且 generator 未損毀，牌局仍可打完")


def test_new_game_option_validation() -> None:
    """ERR-2：TableOptions.from_msg 逐欄位驗證。"""
    ok, err = nm.TableOptions.from_msg({}, True)
    assert err is None and ok is not None and ok.contest is True

    ok, err = nm.TableOptions.from_msg(
        {"dealer_idx": 1, "consecutive": 2, "seat_winds": ["東", "南", "西", "北"],
         "game_round_wind": "南", "contest": False}, True)
    assert err is None and ok is not None
    assert (ok.dealer_idx, ok.consecutive, ok.game_round_wind) == (1, 2, "南")

    bad_msgs = [
        ({"dealer_idx": 99}, "dealer_idx"),
        ({"dealer_idx": "x"}, "dealer_idx"),
        ({"dealer_idx": 1.5}, "dealer_idx"),
        ({"dealer_idx": True}, "dealer_idx"),
        ({"consecutive": "abc"}, "consecutive"),
        ({"consecutive": -5}, "consecutive"),
        ({"consecutive": 10 ** 9}, "consecutive"),
        ({"consecutive": 3}, "dealer_idx"),          # 連莊需一併指定莊家
        ({"seat_winds": ["東"]}, "seat_winds"),
        ({"seat_winds": ["東", "南", "西", "火"]}, "seat_winds"),
        ({"seat_winds": ["東", "東", "南", "西"]}, "seat_winds"),
        ({"seat_winds": {"a": 1}}, "seat_winds"),
        ({"game_round_wind": "火"}, "game_round_wind"),
        ({"contest": "yes"}, "contest"),
    ]
    for msg, keyword in bad_msgs:
        opts, err = nm.TableOptions.from_msg(msg, True)
        assert opts is None and err is not None, f"{msg} 應被拒絕"
        assert keyword in err, (msg, err)
    print(f"  {len(bad_msgs)} 組非法 new_game 參數全被連線層擋下")


class _ProbeClient:
    """直接對某席位的 WebSocket 送出任意訊息，收集伺服器回應。"""

    def __init__(self, port: int, token: str) -> None:
        self.url = f"ws://{HOST}:{port}/ws?t={token}"
        self.ws: websockets.ClientConnection | None = None

    async def __aenter__(self) -> "_ProbeClient":
        self.ws = await websockets.connect(self.url)
        await self.drain()
        return self

    async def __aexit__(self, *exc) -> None:
        if self.ws is not None:
            await self.ws.close()

    async def drain(self, timeout: float = 0.8) -> list[dict]:
        """收掉目前佇列中的訊息。"""
        out: list[dict] = []
        assert self.ws is not None
        try:
            while True:
                out.append(json.loads(await asyncio.wait_for(self.ws.recv(), timeout)))
        except asyncio.TimeoutError:
            return out

    async def send(self, payload: dict, timeout: float = 1.5) -> list[dict]:
        """送出一則訊息並收集回應。"""
        assert self.ws is not None
        await self.ws.send(json.dumps(payload))
        return await self.drain(timeout)

    async def start_and_wait(self, phase: str = "human_discard") -> dict | None:
        """開局並等到出現指定 phase 的 state（含 send 當下就收到的那批）。"""
        replies = await self.send({"cmd": "new_game"}, timeout=3.0)
        for r in replies:
            if r["t"] == "state" and r["v"]["phase"] == phase:
                return r["v"]
        return await self.wait_phase(phase)

    async def wait_phase(self, phase: str, tries: int = 40) -> dict | None:
        """等到出現指定 phase 的 state。"""
        assert self.ws is not None
        for _ in range(tries):
            try:
                msg = json.loads(await asyncio.wait_for(self.ws.recv(), 10))
            except asyncio.TimeoutError:
                return None
            if msg["t"] == "state" and msg["v"]["phase"] == phase:
                return msg["v"]
        return None


async def test_malformed_input_does_not_kill_table() -> None:
    """ERR-1／ERR-2：畸形訊息只回錯給送出者，牌局照常進行。

    這是修補前最嚴重的問題：任何一位玩家（或前端的一個 bug）送出一則畸形
    訊息，就會讓 driver task 死亡、四個人的牌局一起報銷。
    """
    port = SEC_PORT + 2
    async with _one_seat_server(port, SEC_TOKEN) as table:
        async with _ProbeClient(port, SEC_TOKEN) as c:
            state = await c.start_and_wait("human_discard")
            assert state is not None, "未進入出牌階段"
            hand_size = len(state["your_hand"])

            bad_discards = [
                ("../../etc/passwd", "字串路徑"),
                ("abc", "非數字字串"),
                ("0", "數字字串（型別仍不對）"),
                (-1, "負數索引"),
                (hand_size, "剛好越界"),
                (hand_size + 500, "大幅越界"),
                (1.5, "浮點數"),
                (True, "布林值"),
                (None, "缺少 idx"),
                ({"$ne": 1}, "巢狀物件"),
                ([0], "陣列"),
            ]
            for bad, label in bad_discards:
                replies = await c.send({"cmd": "discard", "idx": bad})
                errs = [r for r in replies if r["t"] == "error"]
                assert errs, f"discard {label}（{bad!r}）應回報錯誤，實得 {replies}"
                assert not table._driver.done(), f"discard {label} 讓牌局死亡"

            bad_actions = [
                ("chi:99", "吃牌索引越界"),
                ("y", "此刻不是提示階段"),
                (5, "非字串"),
                ("y" * 100, "超長字串"),
            ]
            for bad, label in bad_actions:
                replies = await c.send({"cmd": "action", "action": bad})
                assert [r for r in replies if r["t"] == "error"], \
                    f"action {label}（{bad!r}）應回報錯誤"
                assert not table._driver.done(), f"action {label} 讓牌局死亡"

            bad_games = [
                {"cmd": "new_game", "dealer_idx": 99},
                {"cmd": "new_game", "seat_winds": ["東"]},
                {"cmd": "new_game", "consecutive": "abc"},
                {"cmd": "new_game", "contest": "yes"},
            ]
            for payload in bad_games:
                replies = await c.send(payload)
                assert [r for r in replies if r["t"] == "error"], \
                    f"{payload} 應回報錯誤"
                assert not table._driver.done(), f"{payload} 讓牌局死亡"

            # 非 JSON 物件的訊息也要有禮貌地回錯，而不是把連線炸掉
            replies = await c.send([1, 2, 3])
            assert [r for r in replies if r["t"] == "error"], "JSON 陣列應回報錯誤"

            # 最重要的驗收：以上全部之後，牌局仍在原地等同一位玩家出牌
            assert not table._driver.done(), "牌局不該因為畸形輸入而終止"
            assert table._session is not None
            assert table._session.current_seat == 0
            assert table._session.current_phase == "human_discard"

            # 合法出牌仍然成功
            replies = await c.send({"cmd": "discard", "idx": 0})
            assert not [r for r in replies if r["t"] == "error"], replies
            assert any(r["t"] == "state" for r in replies), "合法出牌應推進牌局"

    print(f"  {len(bad_discards) + len(bad_actions) + len(bad_games) + 1} 則畸形訊息"
          f"全部只回錯給送出者，牌局未中斷，之後仍能正常出牌")


# ---------------------------------------------------------------------------

def main() -> int:
    """依序執行所有測試。"""
    print("[1] 引擎層多席位視角")
    test_multi_seat_engine()
    test_invalid_human_seats()
    print("[2] 競賽模式資訊隔離")
    test_private_events()
    print("[3] AI 代打")
    test_ai_takeover_engine()
    print("[4] 單人模式向下相容")
    test_single_player_compat()
    print("[5] CLI 參數")
    test_cli_args()
    print("[6] 端到端連線對局")
    asyncio.run(test_end_to_end())
    print("[7] 存取控制（席位 token／Origin）")
    asyncio.run(test_seat_token())
    asyncio.run(test_origin_check())
    print("[8] 輸入驗證（discard 索引／new_game 參數）")
    test_engine_param_validation()
    test_engine_response_validation()
    test_new_game_option_validation()
    asyncio.run(test_malformed_input_does_not_kill_table())
    print("\n全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
