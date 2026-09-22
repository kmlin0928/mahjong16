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
"""
from __future__ import annotations

import asyncio
import json
import random
import sys

import websockets

import mahjong
import net_mahjong as nm
from mahjong import GameSession

HOST = "127.0.0.1"
PORTS = {0: 18901, 1: 18902}


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
        async with websockets.connect(f"ws://{HOST}:{self.port}/ws") as ws:
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
                     disconnect_grace=1.0, afk_seconds=0.0, auto_start=True)
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
    print("\n全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
