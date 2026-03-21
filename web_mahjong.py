# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi",
#   "uvicorn[standard]",
# ]
# ///
"""FastAPI 網頁後端，搭配 GameSession 提供麻將競賽模式的 REST API 與 WebSocket 串流。"""
from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mahjong import GameSession, GameState, HUMAN_PLAYER

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="麻將競賽模式")

# 單一全域 session（單人遊戲）
_session: GameSession | None = None


def _state_to_json(state: GameState) -> dict:
    """將 GameState dataclass 轉為可 JSON 序列化的 dict。"""
    d = dataclasses.asdict(state)
    # scores 含 tuple，轉為 list of list
    if d.get("scores"):
        d["scores"] = [list(s) for s in d["scores"]]
    return d


@app.get("/")
def index() -> FileResponse:
    """回傳前端主頁。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/new_game")
def new_game(contest: bool = True) -> JSONResponse:
    """建立新牌局，推進至首個人類決策點。

    Args:
        contest: 競賽模式（AI 手牌隱藏），預設 True
    """
    global _session
    _session = GameSession(contest=contest)
    state = _session.start()
    return JSONResponse(_state_to_json(state))


@app.post("/discard")
def discard(idx: int) -> JSONResponse:
    """人類出牌，傳入手牌索引，推進遊戲。

    Args:
        idx: 手牌索引（0 起算）
    """
    if _session is None:
        raise HTTPException(status_code=400, detail="尚未開始遊戲，請先 POST /new_game")
    state = _session.respond(str(idx))
    return JSONResponse(_state_to_json(state))


@app.post("/action")
def action(type: str) -> JSONResponse:
    """回應提示（吃碰槓胡），推進遊戲。

    Args:
        type: "y"（接受）| "n"（跳過）| "chi:N"（選擇第 N 種吃法）
    """
    if _session is None:
        raise HTTPException(status_code=400, detail="尚未開始遊戲，請先 POST /new_game")
    state = _session.respond(type)
    return JSONResponse(_state_to_json(state))


@app.websocket("/ws")
async def ws_game(ws: WebSocket) -> None:
    """WebSocket 遊戲主通道。

    接收指令並推送回應：
    - 收：``{"cmd": "new_game", "contest": true}``
    - 收：``{"cmd": "discard", "idx": N}``
    - 收：``{"cmd": "action", "action": "y"|"n"|"chi:N"}``
    - 送（多次）：``{"t": "log", "v": "<事件文字>"}``
    - 送（一次）：``{"t": "state", "v": <GameState dict>}``
    """
    await ws.accept()
    session: GameSession | None = None

    async def _push(state: GameState) -> None:
        """逐行推送 log，最後推送完整 state。"""
        for line in state.log:
            await ws.send_json({"t": "log", "v": line})
            await asyncio.sleep(0.06)
        await ws.send_json({"t": "state", "v": _state_to_json(state)})

    try:
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("cmd")

            if cmd == "new_game":
                contest = bool(msg.get("contest", True))
                dealer_idx_override = msg.get("dealer_idx")  # int or None
                consecutive = int(msg.get("consecutive", 0))
                game_wind_override = msg.get("game_wind")    # str or None
                session = GameSession(
                    contest=contest,
                    dealer_idx_override=dealer_idx_override,
                    consecutive=consecutive,
                    game_wind_override=game_wind_override,
                )
                state = await asyncio.to_thread(session.start)

            elif cmd == "discard":
                if session is None:
                    await ws.send_json({"t": "error", "v": "尚未開局"})
                    continue
                state = await asyncio.to_thread(session.respond, str(msg.get("idx", 0)))

            elif cmd == "action":
                if session is None:
                    await ws.send_json({"t": "error", "v": "尚未開局"})
                    continue
                state = await asyncio.to_thread(session.respond, str(msg.get("action", "n")))

            else:
                await ws.send_json({"t": "error", "v": f"未知指令: {cmd!r}"})
                continue

            await _push(state)

    except WebSocketDisconnect:
        pass


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
