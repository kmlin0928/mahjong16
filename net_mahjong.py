# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi",
#   "uvicorn[standard]",
# ]
# ///
"""多人連線對戰後端：為 1～4 位遠端玩家各開一個連接埠，共用同一牌局。

設計重點
--------
* **一席一埠**：第 i 位玩家連到第 i 個連接埠，該埠的網頁固定綁定一個席位，
  不必在畫面上挑座位，也不會誤點到別人的席位。
* **單一牌局**：四個埠背後只有一個 :class:`mahjong.GameSession`，由本模組的
  :class:`Table` 以 asyncio 驅動，輪到誰就等誰的回應。
* **非玩家一律 AI**：沒有分配給真人的席位，以及離線／逾時的真人席位，
  全部沿用 ``mahjong.py`` 既有的 AI 演算法（``calculate_gates`` +
  ``decide_play``，碰吃必吃、槓依 ``AI_AUTO_KONG``、見胡必胡），
  不另外寫一套策略。

執行方式
--------
.. code-block:: bash

    # 三位玩家，連接埠 8001/8002/8003，第 4 席由 AI 補位
    uv run net_mahjong.py --players 3

    # 指定席位與連接埠：0 號席走 9000、2 號席走 9001
    uv run net_mahjong.py --seats 0 2 --ports 9000 9001

    # 四人連線，離線 15 秒後由 AI 代打，玩家發呆 60 秒也由 AI 代打
    uv run net_mahjong.py --players 4 --disconnect-grace 15 --afk-seconds 60

WebSocket 協定（每個連接埠的 ``/ws``）
--------------------------------------
收（client → server）::

    {"cmd": "new_game", "contest": true, "dealer_idx": N, "consecutive": N,
     "seat_winds": [...], "game_round_wind": "東"}
    {"cmd": "discard", "idx": N}
    {"cmd": "action",  "action": "y" | "n" | "chi:N"}
    {"cmd": "sync"}                       # 重新索取目前盤面

送（server → client）::

    {"t": "hello",  "v": {"seat": N, "seat_wind_hint": null, "human_seats": [...],
                          "seat_ports": {"0": 8001, ...}, "contest": true}}
    {"t": "lobby",  "v": {"online": [...], "connected": [...], "running": bool}}
    {"t": "log",    "v": "<事件文字>"}     # 多次
    {"t": "state",  "v": <GameState dict>} # 一次，收尾
    {"t": "error",  "v": "<訊息>"}
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import signal
import sys
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mahjong import GameSession, GameState

STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_BASE_PORT = 8001
SEAT_COUNT = 4
_POLL_INTERVAL = 0.5          # 等待玩家回應時的輪詢間隔（秒）


def state_to_json(state: GameState) -> dict:
    """將 GameState dataclass 轉為可 JSON 序列化的 dict。

    Args:
        state: 遊戲快照

    Returns:
        可直接丟給 ``send_json`` 的 dict；``scores`` 中的 tuple 轉為 list。
    """
    d = dataclasses.asdict(state)
    if d.get("scores"):
        d["scores"] = [list(s) for s in d["scores"]]
    return d


# ---------------------------------------------------------------------------
# 連線與待回應狀態
# ---------------------------------------------------------------------------

@dataclass
class Connection:
    """一條玩家的 WebSocket 連線。

    Attributes:
        ws:     WebSocket 物件
        seat:   綁定席位（由連接埠決定，client 不可更改）
        cursor: 事件流游標（已推送到第幾筆 ``GameSession`` 事件）
    """
    ws: WebSocket
    seat: int
    cursor: int = 0


@dataclass
class Pending:
    """目前等待中的玩家決策。

    Attributes:
        seat:   該由哪一席回應
        future: 收到回應後 set_result 的 Future
        since:  開始等待的時刻（``loop.time()``）
    """
    seat: int
    future: asyncio.Future
    since: float


@dataclass
class TableOptions:
    """開局參數（對應 ``GameSession`` 的建構子，由前端帶入）。"""
    contest: bool = True
    dealer_idx: int | None = None
    consecutive: int = 0
    seat_winds: list[str] | None = None
    game_round_wind: str | None = None

    @classmethod
    def from_msg(cls, msg: dict, default_contest: bool) -> "TableOptions":
        """由 ``new_game`` 指令建立開局參數。"""
        seat_winds_raw = msg.get("seat_winds")
        return cls(
            contest=bool(msg.get("contest", default_contest)),
            dealer_idx=msg.get("dealer_idx"),
            consecutive=int(msg.get("consecutive", 0) or 0),
            seat_winds=list(seat_winds_raw) if seat_winds_raw else None,
            game_round_wind=msg.get("game_round_wind") or None,
        )


# ---------------------------------------------------------------------------
# Table：共用同一牌局的多席協調器
# ---------------------------------------------------------------------------

class Table:
    """協調 1～4 個真人席位共用單一 :class:`GameSession`。

    執行緒／並行模型：

    * 只有一個 driver task 推進牌局；``GameSession`` 的同步呼叫一律包在
      ``asyncio.to_thread`` 中，並由 ``self._lock`` 保護，避免與其他協程
      同時讀寫牌局狀態。
    * 玩家回應透過 :meth:`submit` 餵給 driver 正在等待的 Future。
    * 離線／逾時由 :meth:`_await_response` 的輪詢負責，改呼叫
      ``GameSession.ai_suggestion()`` 取得 AI 的動作，牌局不會卡住。
    """

    def __init__(
        self,
        seats: list[int],
        seat_ports: dict[int, int],
        contest: bool = True,
        disconnect_grace: float = 15.0,
        afk_seconds: float = 0.0,
        auto_start: bool = True,
    ) -> None:
        """初始化牌桌。

        Args:
            seats:            由真人操作的席位（1–4 個，0–3）
            seat_ports:       席位 → 連接埠，供前端顯示
            contest:          競賽模式（他家手牌不外洩）
            disconnect_grace: 輪到的玩家已離線多久（秒）後交給 AI 代打
            afk_seconds:      玩家在線但未回應多久（秒）後交給 AI 代打；0 為不限時
            auto_start:       所有真人席位都連上線時自動開局
        """
        self.seats = sorted(seats)
        self.seat_ports = seat_ports
        self.contest = contest
        self.disconnect_grace = disconnect_grace
        self.afk_seconds = afk_seconds
        self.auto_start = auto_start

        self._conns: dict[int, list[Connection]] = {s: [] for s in self.seats}
        self._offline_since: dict[int, float] = {}
        self._session: GameSession | None = None
        self._pending: Pending | None = None
        self._driver: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._started_once = False

    # ------------------------------------------------------------------
    # 連線管理
    # ------------------------------------------------------------------

    @property
    def connected_seats(self) -> list[int]:
        """目前有 WebSocket 連上的席位。"""
        return [s for s in self.seats if self._conns[s]]

    def _lobby_payload(self) -> dict:
        """大廳狀態（誰連上了、牌局是否進行中）。"""
        return {
            "connected": self.connected_seats,
            "online": self._session.online_seats if self._session else self.connected_seats,
            "human_seats": self.seats,
            "seat_ports": {str(k): v for k, v in self.seat_ports.items()},
            "running": self._driver is not None and not self._driver.done(),
        }

    async def attach(self, conn: Connection) -> None:
        """接上一條連線：送出 hello、補齊事件、廣播大廳狀態。"""
        self._conns[conn.seat].append(conn)
        self._offline_since.pop(conn.seat, None)
        if self._session is not None:
            self._session.set_seat_online(conn.seat, True)
        await self._safe_send(conn, {
            "t": "hello",
            "v": {
                "seat": conn.seat,
                "human_seats": self.seats,
                "seat_ports": {str(k): v for k, v in self.seat_ports.items()},
                "contest": self.contest,
            },
        })
        await self.broadcast_lobby()
        await self.sync(conn)
        if self.auto_start and not self._started_once and self._all_seats_connected():
            await self.start_game(TableOptions(contest=self.contest))

    async def detach(self, conn: Connection) -> None:
        """移除一條連線；該席若已無連線則標記離線，交由 AI 代打。"""
        conns = self._conns.get(conn.seat, [])
        if conn in conns:
            conns.remove(conn)
        if not conns:
            self._offline_since[conn.seat] = asyncio.get_running_loop().time()
            if self._session is not None:
                self._session.set_seat_online(conn.seat, False)
        await self.broadcast_lobby()

    def _all_seats_connected(self) -> bool:
        """所有真人席位是否都已連上線。"""
        return all(self._conns[s] for s in self.seats)

    async def broadcast_lobby(self) -> None:
        """把大廳狀態推給所有連線。"""
        payload = {"t": "lobby", "v": self._lobby_payload()}
        for seat in self.seats:
            for conn in list(self._conns[seat]):
                await self._safe_send(conn, payload)

    async def _safe_send(self, conn: Connection, payload: dict) -> None:
        """送出訊息，連線已斷則安靜忽略。"""
        try:
            await conn.ws.send_json(payload)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 盤面推送
    # ------------------------------------------------------------------

    async def sync(self, conn: Connection) -> None:
        """把目前盤面（含該席尚未收到的事件）推給單一連線。"""
        if self._session is None:
            return
        async with self._lock:
            payloads = self._render_for(conn)
        await self._deliver(conn, payloads)

    def _render_for(self, conn: Connection) -> tuple[list[str], dict]:
        """（需持有 _lock）產生單一連線的事件差集與盤面快照。"""
        assert self._session is not None
        state = self._session.view(conn.seat)
        events = self._session.events(conn.cursor, conn.seat)
        conn.cursor = state.event_index
        return events, state_to_json(state)

    async def _deliver(self, conn: Connection, payloads: tuple[list[str], dict]) -> None:
        """依序送出事件文字，最後送出盤面快照。"""
        events, state = payloads
        for line in events:
            await self._safe_send(conn, {"t": "log", "v": line})
        await self._safe_send(conn, {"t": "state", "v": state})

    async def broadcast_state(self) -> None:
        """把最新盤面推給所有連線（各席各自的視角與事件）。"""
        if self._session is None:
            return
        async with self._lock:
            batch = [
                (conn, self._render_for(conn))
                for seat in self.seats
                for conn in list(self._conns[seat])
            ]
        for conn, payloads in batch:
            await self._deliver(conn, payloads)

    # ------------------------------------------------------------------
    # 牌局驅動
    # ------------------------------------------------------------------

    async def start_game(self, opts: TableOptions) -> None:
        """（重新）開局：取消舊的 driver，建立新的 GameSession 並推進。"""
        if self._driver is not None and not self._driver.done():
            self._driver.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._driver
        self._pending = None
        for conn_list in self._conns.values():
            for conn in conn_list:
                conn.cursor = 0
        self._started_once = True
        # 通知所有連線清空事件記錄與覆蓋層（事件游標已歸零，將整段重播）
        for seat in self.seats:
            for conn in list(self._conns[seat]):
                await self._safe_send(conn, {"t": "reset", "v": None})
        self._driver = asyncio.create_task(self._run_game(opts))

    async def _run_game(self, opts: TableOptions) -> None:
        """driver task：建立牌局並一路推進到結束。"""
        session = GameSession(
            contest=opts.contest,
            dealer_idx_override=opts.dealer_idx,
            consecutive=opts.consecutive,
            seat_winds=opts.seat_winds,
            game_round_wind=opts.game_round_wind,
            human_seats=self.seats,
        )
        for seat in self.seats:
            session.set_seat_online(seat, bool(self._conns[seat]))
        self._session = session

        try:
            async with self._lock:
                state = await asyncio.to_thread(session.start)
            while True:
                await self.broadcast_state()
                if state.phase == "game_over":
                    break
                resp = await self._await_response(state.current_seat)
                async with self._lock:
                    state = await asyncio.to_thread(session.respond, resp)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - 防止 driver 靜默死亡
            await self._broadcast_error(f"牌局發生錯誤：{exc!r}")
            raise
        finally:
            self._pending = None
        await self.broadcast_lobby()

    async def _broadcast_error(self, msg: str) -> None:
        """把錯誤訊息推給所有連線。"""
        for seat in self.seats:
            for conn in list(self._conns[seat]):
                await self._safe_send(conn, {"t": "error", "v": msg})

    async def _await_response(self, seat: int) -> str:
        """等待指定席位回應；離線或逾時則改由 AI 代打。

        Args:
            seat: 待回應席位

        Returns:
            可直接餵給 ``GameSession.respond()`` 的回應字串。
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending = Pending(seat=seat, future=fut, since=loop.time())
        try:
            while not fut.done():
                try:
                    return await asyncio.wait_for(
                        asyncio.shield(fut), _POLL_INTERVAL
                    )
                except asyncio.TimeoutError:
                    pass
                reason = self._takeover_reason(seat, loop.time())
                if reason is not None and not fut.done():
                    await self._takeover(fut, seat, reason)
            return fut.result()
        finally:
            self._pending = None

    def _takeover_reason(self, seat: int, now: float) -> str | None:
        """判斷是否該讓 AI 代打，回傳原因字串；不需代打時回傳 None。"""
        offline_at = self._offline_since.get(seat)
        if offline_at is not None and not self._conns[seat]:
            if now - offline_at >= self.disconnect_grace:
                return "離線"
        if self.afk_seconds > 0 and self._pending is not None:
            if now - self._pending.since >= self.afk_seconds:
                return "逾時"
        return None

    async def _takeover(self, fut: asyncio.Future, seat: int, reason: str) -> None:
        """以既有 AI 演算法代替該席位做出決定。"""
        assert self._session is not None
        async with self._lock:
            if fut.done():
                return
            resp = await asyncio.to_thread(self._session.ai_suggestion)
            label = self._session.seat_wind(seat)
            self._session.note(f"{label} {reason}，本手改由 AI 代打")
        if not fut.done():
            fut.set_result(resp)

    def submit(self, seat: int, resp: str) -> str | None:
        """接受某席位的回應。

        Args:
            seat: 送出回應的席位（由連接埠決定，無法偽造）
            resp: 回應字串

        Returns:
            成功時回傳 None，否則回傳給前端的錯誤訊息。
        """
        pending = self._pending
        if pending is None or pending.future.done():
            return "目前沒有等待中的決策"
        if pending.seat != seat:
            return f"還沒輪到你（等待席位 {pending.seat}）"
        pending.future.set_result(resp)
        return None

    async def shutdown(self) -> None:
        """關閉牌桌，取消 driver task。"""
        if self._driver is not None and not self._driver.done():
            self._driver.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._driver


# ---------------------------------------------------------------------------
# 每個席位一個 FastAPI app（綁定固定席位）
# ---------------------------------------------------------------------------

def create_seat_app(table: Table, seat: int) -> FastAPI:
    """建立綁定於單一席位的 FastAPI app。

    Args:
        table: 共用牌桌
        seat:  此連接埠代表的席位（0–3）

    Returns:
        可交給 uvicorn 執行的 FastAPI app。
    """
    app = FastAPI(title=f"麻將連線對戰 — 席位 {seat}")

    @app.get("/")
    def index() -> FileResponse:
        """回傳前端主頁。"""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/seat")
    def seat_info() -> JSONResponse:
        """回傳此連接埠綁定的席位與牌桌組成（供前端初始化）。"""
        return JSONResponse({
            "seat": seat,
            "human_seats": table.seats,
            "seat_ports": {str(k): v for k, v in table.seat_ports.items()},
            "contest": table.contest,
        })

    @app.websocket("/ws")
    async def ws_game(ws: WebSocket) -> None:
        """此席位的遊戲主通道。"""
        await ws.accept()
        conn = Connection(ws=ws, seat=seat)
        await table.attach(conn)
        try:
            while True:
                msg = await ws.receive_json()
                cmd = msg.get("cmd")

                if cmd == "new_game":
                    await table.start_game(TableOptions.from_msg(msg, table.contest))
                elif cmd == "discard":
                    err = table.submit(seat, str(msg.get("idx", 0)))
                    if err:
                        await ws.send_json({"t": "error", "v": err})
                elif cmd == "action":
                    err = table.submit(seat, str(msg.get("action", "n")))
                    if err:
                        await ws.send_json({"t": "error", "v": err})
                elif cmd == "sync":
                    conn.cursor = 0
                    await table.sync(conn)
                else:
                    await ws.send_json({"t": "error", "v": f"未知指令: {cmd!r}"})
        except WebSocketDisconnect:
            pass
        finally:
            await table.detach(conn)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


# ---------------------------------------------------------------------------
# uvicorn：同一行程內同時跑多個連接埠
# ---------------------------------------------------------------------------

class _SharedSignalServer(uvicorn.Server):
    """停用 uvicorn 內建訊號處理，改由 :func:`serve_all` 統一控管。

    多個 Server 共用同一個事件迴圈時，各自 ``loop.add_signal_handler`` 會互相
    覆寫，導致 Ctrl-C 只關掉其中一個連接埠。
    """

    def install_signal_handlers(self) -> None:   # uvicorn < 0.29
        """不安裝訊號處理（由外層統一處理）。"""
        return None

    @contextlib.contextmanager
    def capture_signals(self):                   # uvicorn >= 0.29
        """不攔截訊號（由外層統一處理）。"""
        yield


async def serve_all(table: Table, host: str, seat_ports: dict[int, int]) -> None:
    """同時啟動每個席位的 HTTP/WebSocket 服務，直到收到中止訊號。

    Args:
        table:      共用牌桌
        host:       監聽位址
        seat_ports: 席位 → 連接埠
    """
    servers = [
        _SharedSignalServer(
            uvicorn.Config(
                create_seat_app(table, seat),
                host=host,
                port=port,
                log_level="warning",
            )
        )
        for seat, port in sorted(seat_ports.items())
    ]

    loop = asyncio.get_running_loop()

    def _stop() -> None:
        for srv in servers:
            srv.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop)

    try:
        await asyncio.gather(*(srv.serve() for srv in servers))
    finally:
        await table.shutdown()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def resolve_seats_ports(args: argparse.Namespace) -> tuple[list[int], dict[int, int]]:
    """由命令列參數推導「哪些席位是真人」與「各席位用哪個連接埠」。

    Args:
        args: 已解析的命令列參數

    Returns:
        (席位列表, 席位→連接埠)

    Raises:
        SystemExit: 參數組合不合法（人數、席位範圍、埠數不符、重複）。
    """
    if args.seats:
        seats = [int(s) for s in args.seats]
    else:
        seats = list(range(args.players))

    if not 1 <= len(seats) <= SEAT_COUNT:
        raise SystemExit(f"玩家人數需為 1–{SEAT_COUNT}，收到 {len(seats)} 位")
    if len(set(seats)) != len(seats):
        raise SystemExit(f"席位不可重複：{seats}")
    if any(s < 0 or s >= SEAT_COUNT for s in seats):
        raise SystemExit(f"席位僅接受 0–{SEAT_COUNT - 1}，收到 {seats}")

    if args.ports:
        ports = [int(p) for p in args.ports]
        if len(ports) != len(seats):
            raise SystemExit(
                f"連接埠數量（{len(ports)}）需與玩家人數（{len(seats)}）相同"
            )
    else:
        ports = [args.base_port + i for i in range(len(seats))]
    if len(set(ports)) != len(ports):
        raise SystemExit(f"連接埠不可重複：{ports}")

    return sorted(seats), dict(zip(sorted(seats), ports))


def build_parser() -> argparse.ArgumentParser:
    """建立命令列參數剖析器。"""
    p = argparse.ArgumentParser(
        prog="net_mahjong.py",
        description="16 張麻將多人連線對戰：一位玩家一個連接埠，空席由 AI 補位。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例：\n"
            "  uv run net_mahjong.py --players 2\n"
            "  uv run net_mahjong.py --seats 0 2 --ports 9000 9001\n"
            "  uv run net_mahjong.py --players 4 --afk-seconds 60\n"
        ),
    )
    p.add_argument("--players", type=int, default=1,
                   help=f"遠端玩家人數 1–{SEAT_COUNT}（預設 1），席位依序由 0 起算")
    p.add_argument("--seats", type=int, nargs="+", default=None,
                   help="明確指定真人席位（0–3），會覆蓋 --players")
    p.add_argument("--ports", type=int, nargs="+", default=None,
                   help="明確指定各席位的連接埠（數量需等於玩家人數）")
    p.add_argument("--base-port", type=int, default=DEFAULT_BASE_PORT,
                   help=f"未指定 --ports 時的起始連接埠（預設 {DEFAULT_BASE_PORT}）")
    p.add_argument("--host", default="0.0.0.0",
                   help="監聽位址（預設 0.0.0.0，僅本機可改用 127.0.0.1）")
    p.add_argument("--no-contest", dest="contest", action="store_false",
                   help="關閉競賽模式（他家手牌與補摸牌面不再隱藏）")
    p.add_argument("--disconnect-grace", type=float, default=15.0,
                   help="輪到的玩家離線幾秒後由 AI 代打（預設 15）")
    p.add_argument("--afk-seconds", type=float, default=0.0,
                   help="玩家在線但未回應幾秒後由 AI 代打；0 表不限時（預設 0）")
    p.add_argument("--no-auto-start", dest="auto_start", action="store_false",
                   help="所有玩家連上線時不自動開局，改由任一玩家按「開始對局」")
    p.set_defaults(contest=True, auto_start=True)
    return p


def main(argv: list[str] | None = None) -> int:
    """命令列進入點。"""
    args = build_parser().parse_args(argv)
    seats, seat_ports = resolve_seats_ports(args)

    table = Table(
        seats=seats,
        seat_ports=seat_ports,
        contest=args.contest,
        disconnect_grace=args.disconnect_grace,
        afk_seconds=args.afk_seconds,
        auto_start=args.auto_start,
    )

    ai_seats = [s for s in range(SEAT_COUNT) if s not in seats]
    print("─" * 56)
    print(f"麻將多人連線對戰｜真人 {len(seats)} 位，AI {len(ai_seats)} 位")
    for seat, port in sorted(seat_ports.items()):
        print(f"  席位 {seat} → http://{args.host}:{port}/")
    if ai_seats:
        print(f"  AI 席位：{', '.join(str(s) for s in ai_seats)}（沿用既有 AI 演算法）")
    print(f"  競賽模式：{'開' if args.contest else '關'}"
          f"｜離線代打 {args.disconnect_grace:g}s"
          f"｜發呆代打 {'關' if args.afk_seconds <= 0 else f'{args.afk_seconds:g}s'}")
    print("─" * 56)

    try:
        asyncio.run(serve_all(table, args.host, seat_ports))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
