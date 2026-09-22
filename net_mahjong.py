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

存取控制
--------
* **席位 token**：啟動時為每個席位產生一組隨機 token，並印在該席的網址裡
  （``http://127.0.0.1:8001/?t=<token>``）。連接埠只決定「席位編號」，
  token 才決定「誰有權操作這個席位」——沒有 token 的人即使連得到該埠也
  拿不到手牌。瀏覽器開過帶 token 的網址後，token 會以 ``HttpOnly`` +
  ``SameSite=Strict`` cookie 保存，之後直接開 ``/`` 即可。
* **Origin 檢查**：WebSocket 不受同源政策保護，因此握手時會比對 ``Origin``
  與 ``Host``；不符即拒絕，阻擋跨站 WebSocket 劫持（CSWSH）。沒有 ``Origin``
  標頭的非瀏覽器客戶端（如測試腳本）則靠 token 把關。
* **預設只聽本機**：``--host`` 預設 ``127.0.0.1``。要讓同網段的朋友連進來
  才需明確指定 ``--host 0.0.0.0``，此時務必把帶 token 的網址個別傳給本人。

執行方式
--------
.. code-block:: bash

    # 三位玩家，連接埠 8001/8002/8003，第 4 席由 AI 補位
    uv run net_mahjong.py --players 3

    # 指定席位與連接埠：0 號席走 9000、2 號席走 9001
    uv run net_mahjong.py --seats 0 2 --ports 9000 9001

    # 四人連線，離線 15 秒後由 AI 代打，玩家發呆 60 秒也由 AI 代打
    uv run net_mahjong.py --players 4 --disconnect-grace 15 --afk-seconds 60

HTTP 端點（每個連接埠）
----------------------
``GET /?t=<token>``      主頁；驗證後把 token 寫成該席專屬 cookie
``GET /seat``            此埠綁定的席位與牌桌組成（需 token 或 cookie）
``GET /static/...``      前端靜態檔
未帶合法 token 的 ``/`` 與 ``/seat`` 一律回 ``401``。

WebSocket 協定（每個連接埠的 ``/ws?t=<token>``）
------------------------------------------------
握手需通過 Origin 檢查與 token 驗證（token 可用查詢參數或 cookie 提供），
未通過者在 ``accept()`` 之前即被拒絕（客戶端看到 HTTP 403）。

所有 client → server 的欄位都經過型別與範圍驗證；不合法時只回
``{"t": "error", ...}`` 給送出者，**不會影響其他三家、也不會終止牌局**。

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
import secrets
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mahjong import (
    MAX_CONSECUTIVE,
    GameSession,
    GameState,
    _SEAT_WIND_NAMES as WIND_NAMES,
)

STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_BASE_PORT = 8001
SEAT_COUNT = 4
_POLL_INTERVAL = 0.5          # 等待玩家回應時的輪詢間隔（秒）
_TOKEN_BYTES = 24             # 席位 token 長度（secrets.token_urlsafe 的參數）

# WebSocket 拒絕碼（4000–4999 為應用自訂範圍）。
# 注意：在 accept() 之前關閉時，uvicorn 會把它轉成 HTTP 403 握手失敗回應，
# 客戶端看到的是 403 而不是這裡的碼——這是刻意的：連線根本不會被建立，
# 未通過驗證的對方拿不到任何牌局資訊。這兩個常數用於伺服器端區分原因。
WS_CLOSE_UNAUTHORIZED = 4401  # token 缺漏或不符
WS_CLOSE_BAD_ORIGIN = 4403    # Origin 與 Host 不符（疑似 CSWSH）


def display_host(host: str) -> str:
    """把監聽位址換成「可以貼給玩家點的」主機位址。

    ``0.0.0.0``／``::`` 是「所有介面」的意思，不能直接當網址用。此時探測本機
    對外的 IP（僅設定 UDP socket 的目的位址，不會真的送出封包），探測失敗就
    退回 ``127.0.0.1``。

    Args:
        host: ``--host`` 指定的監聽位址

    Returns:
        可放進網址的主機位址。
    """
    if host not in ("0.0.0.0", "::"):
        return host
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))     # 不送封包，只為取得出口介面位址
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def seat_cookie_name(seat: int) -> str:
    """回傳該席位的 token cookie 名稱。

    Cookie 不以連接埠區分（同一主機的不同埠共用 cookie jar），因此把席位
    編號放進名稱，避免席位之間互相覆蓋。

    Args:
        seat: 席位（0–3）
    """
    return f"mj_seat{seat}_token"


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
    def from_msg(
        cls, msg: dict, default_contest: bool
    ) -> tuple["TableOptions | None", str | None]:
        """由 ``new_game`` 指令建立開局參數，並驗證每個欄位的邊界。

        這些值全部來自不受信任的遠端客戶端。未經驗證直接送進
        :class:`~mahjong.GameSession`，``dealer_idx``／``seat_winds`` 會在牌局
        中途以 ``IndexError`` 炸掉整桌，``consecutive`` 則會讓 ``int()`` 拋
        ``ValueError`` 而中斷該條 WebSocket。

        Args:
            msg:             ``new_game`` 指令的原始 dict
            default_contest: 未指定 ``contest`` 時採用的預設值

        Returns:
            ``(opts, None)`` 表示驗證通過；``(None, 錯誤訊息)`` 表示參數不合法。
        """
        contest_raw = msg.get("contest", default_contest)
        if not isinstance(contest_raw, bool):
            return None, f"contest 需為布林值，收到 {type(contest_raw).__name__}"

        dealer_idx = msg.get("dealer_idx")
        if dealer_idx is not None:
            if isinstance(dealer_idx, bool) or not isinstance(dealer_idx, int):
                return None, f"dealer_idx 需為整數，收到 {type(dealer_idx).__name__}"
            if not 0 <= dealer_idx < SEAT_COUNT:
                return None, f"dealer_idx 僅接受 0–{SEAT_COUNT - 1}，收到 {dealer_idx}"

        consecutive_raw = msg.get("consecutive", 0)
        if consecutive_raw is None:
            consecutive_raw = 0
        if isinstance(consecutive_raw, bool) or not isinstance(consecutive_raw, int):
            return None, f"consecutive 需為整數，收到 {type(consecutive_raw).__name__}"
        if not 0 <= consecutive_raw <= MAX_CONSECUTIVE:
            return None, (
                f"consecutive 僅接受 0–{MAX_CONSECUTIVE}，收到 {consecutive_raw}"
            )

        seat_winds_raw = msg.get("seat_winds")
        seat_winds: list[str] | None = None
        if seat_winds_raw:
            if not isinstance(seat_winds_raw, list):
                return None, (
                    f"seat_winds 需為四個門風的列表，收到 {type(seat_winds_raw).__name__}"
                )
            if len(seat_winds_raw) != SEAT_COUNT:
                return None, f"seat_winds 需恰好 {SEAT_COUNT} 項，收到 {len(seat_winds_raw)} 項"
            for w in seat_winds_raw:
                if not isinstance(w, str) or w not in WIND_NAMES:
                    return None, (
                        f"seat_winds 僅接受 {'／'.join(WIND_NAMES)}，收到 {w!r}"
                    )
            if len(set(seat_winds_raw)) != SEAT_COUNT:
                return None, f"seat_winds 四家門風不可重複：{seat_winds_raw}"
            seat_winds = list(seat_winds_raw)

        game_round_wind = msg.get("game_round_wind") or None
        if game_round_wind is not None:
            if not isinstance(game_round_wind, str) or game_round_wind not in WIND_NAMES:
                return None, (
                    f"game_round_wind 僅接受 {'／'.join(WIND_NAMES)}，"
                    f"收到 {game_round_wind!r}"
                )

        # consecutive > 0 時 GameSession 要求同時指定 dealer_idx，先擋下來，
        # 否則會在 _game_loop 內以 RuntimeError 終止牌局。
        if consecutive_raw > 0 and dealer_idx is None:
            return None, "指定 consecutive 時需一併指定 dealer_idx"

        return cls(
            contest=contest_raw,
            dealer_idx=dealer_idx,
            consecutive=consecutive_raw,
            seat_winds=seat_winds,
            game_round_wind=game_round_wind,
        ), None


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
        seat_tokens: dict[int, str] | None = None,
    ) -> None:
        """初始化牌桌。

        Args:
            seats:            由真人操作的席位（1–4 個，0–3）
            seat_ports:       席位 → 連接埠，供前端顯示
            contest:          競賽模式（他家手牌不外洩）
            disconnect_grace: 輪到的玩家已離線多久（秒）後交給 AI 代打
            afk_seconds:      玩家在線但未回應多久（秒）後交給 AI 代打；0 為不限時
            auto_start:       所有真人席位都連上線時自動開局
            seat_tokens:      席位 → 存取 token；None 時自動產生。
                              連接埠只決定席位編號，token 才決定操作權。
        """
        self.seats = sorted(seats)
        self.seat_ports = seat_ports
        self.seat_tokens = seat_tokens or {
            s: secrets.token_urlsafe(_TOKEN_BYTES) for s in self.seats
        }
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

    def check_token(self, seat: int, token: str | None) -> bool:
        """以定值時間比對席位 token。

        Args:
            seat:  席位（0–3）
            token: 客戶端提供的 token；None 或空字串一律拒絕

        Returns:
            token 正確時為 True。
        """
        expected = self.seat_tokens.get(seat)
        if not expected or not token:
            return False
        return secrets.compare_digest(token, expected)

    def seat_url(self, host: str, seat: int) -> str:
        """組出該席位的完整入場網址（含 token）。

        Args:
            host: ``--host`` 指定的監聽位址；``0.0.0.0``／``::`` 會換成本機
                  對外的實際 IP，好讓網址可以直接傳給同網段的玩家
            seat: 席位（0–3）
        """
        return (
            f"http://{display_host(host)}:{self.seat_ports[seat]}/"
            f"?t={self.seat_tokens[seat]}"
        )

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

    def _claim_turn(self, seat: int) -> tuple[Pending | None, str | None]:
        """確認現在確實輪到這一席，回傳 (Pending, 錯誤訊息)。"""
        pending = self._pending
        if pending is None or pending.future.done():
            return None, "目前沒有等待中的決策"
        if pending.seat != seat:
            return None, f"還沒輪到你（等待席位 {pending.seat}）"
        if self._session is None:
            return None, "牌局尚未開始"
        return pending, None

    def submit_discard(self, seat: int, raw_idx: object) -> str | None:
        """驗證並接受某席位的出牌。

        ``raw_idx`` 直接來自 WebSocket 的 JSON，型別與範圍都不可信任：

        * 非整數（字串、浮點數、dict）會讓引擎的 ``int()`` 拋 ``ValueError``；
        * 超出手牌張數會拋 ``IndexError``；
        * **負數不會拋錯**，而是靜默打出手牌最後一張——玩家打出的不是他選的牌。

        以上任一情況在修補前都會終止整桌牌局，因此一律在這裡擋下，
        並保持等待狀態讓同一位玩家重送。

        Args:
            seat:    送出回應的席位
            raw_idx: 客戶端提供的手牌索引（原始 JSON 值）

        Returns:
            成功時回傳 None，否則回傳給該玩家的錯誤訊息。
        """
        pending, err = self._claim_turn(seat)
        if err is not None:
            return err
        assert pending is not None and self._session is not None

        if self._session.current_phase != "human_discard":
            return "目前不是出牌階段"
        # 注意：bool 是 int 的子類別，True 會被當成索引 1，必須先排除。
        if isinstance(raw_idx, bool) or not isinstance(raw_idx, int):
            return f"出牌索引需為整數，收到 {type(raw_idx).__name__}"
        size = self._session.hand_size(seat)
        if not 0 <= raw_idx < size:
            return f"出牌索引需介於 0–{size - 1}，收到 {raw_idx}"

        resp = str(raw_idx)
        msg = self._session.check_response(resp)   # 引擎層第二道防線
        if msg is not None:
            return msg
        pending.future.set_result(resp)
        return None

    def submit_action(self, seat: int, raw_action: object) -> str | None:
        """驗證並接受某席位對提示（吃／碰／槓／胡）的回應。

        Args:
            seat:       送出回應的席位
            raw_action: 客戶端提供的動作（原始 JSON 值），應為 "y"／"n"／"chi:N"

        Returns:
            成功時回傳 None，否則回傳給該玩家的錯誤訊息。
        """
        pending, err = self._claim_turn(seat)
        if err is not None:
            return err
        assert pending is not None and self._session is not None

        if self._session.current_phase != "prompt":
            return "目前沒有待回應的提示"
        if not isinstance(raw_action, str):
            return f"action 需為字串，收到 {type(raw_action).__name__}"
        if len(raw_action) > 16:
            return "action 內容過長"

        msg = self._session.check_response(raw_action)
        if msg is not None:
            return msg
        pending.future.set_result(raw_action)
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

def origin_allowed(origin: str | None, host_header: str | None) -> bool:
    """判斷 WebSocket 握手的 ``Origin`` 是否可信。

    WebSocket **不受瀏覽器同源政策保護**：任何網頁都能開 ``ws://`` 連到本機
    服務。若不比對 ``Origin``，玩家只要在對局期間瀏覽到惡意網頁，該網頁就能
    連上這個席位、讀走手牌並代為出牌（跨站 WebSocket 劫持，CSWSH）。

    比對對象取自請求自己的 ``Host`` 標頭，因此不論伺服器綁在 ``127.0.0.1``、
    區網 IP 還是主機名稱都成立，不需要額外設定。

    Args:
        origin:      ``Origin`` 標頭；None 代表非瀏覽器客戶端
        host_header: ``Host`` 標頭

    Returns:
        可放行時為 True。沒有 ``Origin`` 的客戶端（測試腳本、CLI 工具）放行，
        因為它們本來就不受同源政策約束，改由席位 token 把關。
    """
    if origin is None:
        return True
    if not host_header:
        return False
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return parsed.netloc == host_header


def create_seat_app(table: Table, seat: int) -> FastAPI:
    """建立綁定於單一席位的 FastAPI app。

    Args:
        table: 共用牌桌
        seat:  此連接埠代表的席位（0–3）

    Returns:
        可交給 uvicorn 執行的 FastAPI app。
    """
    app = FastAPI(title=f"麻將連線對戰 — 席位 {seat}")
    cookie_name = seat_cookie_name(seat)

    def _token_from(request_token: str | None, cookie_token: str | None) -> str | None:
        """取出要驗證的 token：網址參數優先，其次是先前存下的 cookie。"""
        return request_token or cookie_token

    @app.get("/")
    def index(request: Request, t: str | None = None) -> Response:
        """回傳前端主頁；首次進入需帶 ``?t=<token>``。

        驗證通過後把 token 寫成 ``HttpOnly`` + ``SameSite=Strict`` 的 cookie，
        之後直接開 ``/`` 即可，網址列也不會一直掛著 token。
        """
        token = _token_from(t, request.cookies.get(cookie_name))
        if not table.check_token(seat, token):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": f"需要席位 {seat} 的存取 token，"
                               f"請使用伺服器啟動時印出的網址（含 ?t=...）。",
                },
            )
        resp = FileResponse(STATIC_DIR / "index.html")
        resp.set_cookie(
            cookie_name, token or "",
            httponly=True,        # JavaScript 讀不到，降低 XSS 竊取風險
            samesite="strict",    # 跨站請求不帶此 cookie（含 WS 握手）
            max_age=12 * 3600,
        )
        return resp

    @app.get("/seat")
    def seat_info(request: Request, t: str | None = None) -> JSONResponse:
        """回傳此連接埠綁定的席位與牌桌組成（供前端初始化）。"""
        if not table.check_token(seat, _token_from(t, request.cookies.get(cookie_name))):
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "存取 token 不正確"},
            )
        return JSONResponse({
            "seat": seat,
            "human_seats": table.seats,
            "seat_ports": {str(k): v for k, v in table.seat_ports.items()},
            "contest": table.contest,
        })

    @app.websocket("/ws")
    async def ws_game(ws: WebSocket) -> None:
        """此席位的遊戲主通道。

        握手時依序檢查 ``Origin``（擋 CSWSH）與席位 token（擋任意第三方），
        兩者皆通過才 ``accept()``。
        """
        if not origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
            await ws.close(code=WS_CLOSE_BAD_ORIGIN)
            return
        token = _token_from(
            ws.query_params.get("t") or ws.query_params.get("token"),
            ws.cookies.get(cookie_name),
        )
        if not table.check_token(seat, token):
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        await ws.accept()
        conn = Connection(ws=ws, seat=seat)
        await table.attach(conn)
        try:
            while True:
                msg = await ws.receive_json()
                if not isinstance(msg, dict):
                    await ws.send_json({"t": "error", "v": "訊息需為 JSON 物件"})
                    continue
                cmd = msg.get("cmd")

                if cmd == "new_game":
                    opts, opts_err = TableOptions.from_msg(msg, table.contest)
                    if opts_err is not None:
                        await ws.send_json({"t": "error", "v": opts_err})
                        continue
                    assert opts is not None
                    await table.start_game(opts)
                elif cmd == "discard":
                    err = table.submit_discard(seat, msg.get("idx"))
                    if err:
                        await ws.send_json({"t": "error", "v": err})
                elif cmd == "action":
                    err = table.submit_action(seat, msg.get("action"))
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
    p.add_argument("--host", default="127.0.0.1",
                   help="監聽位址（預設 127.0.0.1，僅限本機；要讓同網段的人連進來"
                        "才改用 0.0.0.0，並個別把帶 token 的網址傳給本人）")
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
    print("─" * 72)
    print(f"麻將多人連線對戰｜真人 {len(seats)} 位，AI {len(ai_seats)} 位")
    print("  每個席位的網址都含專屬 token，請分別傳給該位玩家，不要對外張貼：")
    for seat in seats:
        print(f"  席位 {seat} → {table.seat_url(args.host, seat)}")
    if ai_seats:
        print(f"  AI 席位：{', '.join(str(s) for s in ai_seats)}（沿用既有 AI 演算法）")
    print(f"  競賽模式：{'開' if args.contest else '關'}"
          f"｜離線代打 {args.disconnect_grace:g}s"
          f"｜發呆代打 {'關' if args.afk_seconds <= 0 else f'{args.afk_seconds:g}s'}")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"  ⚠ 監聽於 {args.host}：本機以外也連得到，請確認網路環境可信"
              f"（連線未加密，建議僅用於信任的區網）")
    print("─" * 72)

    try:
        asyncio.run(serve_all(table, args.host, seat_ports))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
