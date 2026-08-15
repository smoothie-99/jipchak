import json
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..session_manager import SessionManager
from ..stream.relay_hub import RelayHub


def build_router(relay_hub: RelayHub, session_manager: SessionManager) -> APIRouter:
    """
    React 브라우저 클라이언트 WebSocket 핸들러.

    수신:
      - 텍스트 `{"event":"REQUEST_START"}` : 브라우저 시작 버튼.
        활성 세션이 없으면 새 session_id 발급 후 SESSION_START broadcast.
        활성 세션이 있으면 기존 session_id로 SESSION_START 회신.

    송신: msgpack 프레임 + JSON 이벤트(RelayHub fan-out).
    """
    router = APIRouter()

    @router.websocket("/ws/stream")
    async def stream_ws(ws: WebSocket) -> None:
        await ws.accept()
        await relay_hub.subscribe(ws)
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break

                text = msg.get("text")
                if not text:
                    continue

                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue

                if data.get("event") == "REQUEST_START":
                    await _handle_request_start(ws, session_manager, relay_hub)

        except WebSocketDisconnect:
            pass
        finally:
            await relay_hub.unsubscribe(ws)

    return router


async def _handle_request_start(
    ws: WebSocket,
    session_manager: SessionManager,
    relay_hub: RelayHub,
) -> None:
    active = session_manager.get_active_session_id()
    if active is not None:
        # 진행 중 세션이 있으면 거절하지 않고 그 세션으로 합류시킨다.
        try:
            await ws.send_text(json.dumps({
                "event": "SESSION_START",
                "session_id": active,
                "reused": True,
            }))
        except Exception:
            pass
        return

    session_id = f"session_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    await session_manager.start(session_id)
    await relay_hub.broadcast_text(json.dumps({
        "event": "SESSION_START",
        "session_id": session_id,
    }).encode())
    print(f"[ws_browser] REQUEST_START -> SESSION_START broadcast: {session_id}")
