import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import msgpack
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..session_manager import SessionManager
from ..stream.relay_hub import RelayHub
from ..stream.unpacker import FrameUnpacker

_frame_executor = ThreadPoolExecutor(max_workers=1)


def _sync_infer_grasp(session_manager: SessionManager, session_id: str):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(session_manager.infer_grasp(session_id))
    finally:
        loop.close()


def _sync_process_frame(session_manager: SessionManager, session_id: str, payload: bytes):
    frame = FrameUnpacker.unpack(payload)
    if frame is None:
        return
    loop = asyncio.new_event_loop()
    try:
        # 녹화는 웹캠(color_2d), 추론은 D435(color_3d), depth는 그대로
        loop.run_until_complete(
            session_manager.on_frame(
                session_id,
                color_frame_record=frame.color_2d,
                color_frame_infer=frame.color_3d,
                depth_frame=frame.depth_3d,
            )
        )
    finally:
        loop.close()


def build_router(relay_hub: RelayHub, session_manager: SessionManager) -> APIRouter:
    """
    RPi 전용 WebSocket 엔드포인트를 만든다.

    프로토콜:
      - 텍스트 메시지: JSON 제어 신호
            {"event": "START", "session_id": "..."}
            {"event": "STOP",  "session_id": "..."}
      - 바이너리 메시지: FramePacker가 만든 msgpack 페이로드
    """
    router = APIRouter()

    @router.websocket("/ws/camera")
    async def camera_ws(ws: WebSocket) -> None:
        await ws.accept()
        print(f"[ws_rpi] connected from {ws.client}")

        current_session: Optional[str] = None
        last_infer_time: float = 0.0
        last_relay_time: float = 0.0
        relay_interval: float = 0.1  # 10fps cap for browser relay
        # 추론 주기 0.5초 (GPU 환경 가정). overlay 갱신 빈도 ↑ → 사용자 체감 반응성 ↑.
        # CPU 환경에서는 컨테이너 CPU 가 매우 높게 올라가니 주의.
        infer_interval: float = 0.5
        infer_state = {"running": False}

        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break

                # 텍스트 = 제어 신호
                if "text" in msg and msg["text"] is not None:
                    current_session = await _apply_control(
                        msg["text"], session_manager, relay_hub, current_session
                    )
                    continue

                # 바이너리 = 프레임
                payload: bytes = msg.get("bytes") or b""
                if not payload:
                    continue

                # ① 브라우저로 릴레이 (FPS 제한 + fire-and-forget + depth 제거로 대역폭 최적화)
                now = time.monotonic()
                if now - last_relay_time >= relay_interval:
                    last_relay_time = now
                    asyncio.create_task(_relay_without_depth(relay_hub, payload))

                # ws_browser 의 REQUEST_START 로 시작된 세션을 RPi 측에서도 인지하도록
                # 매 프레임마다 SessionManager 의 active id 와 동기화.
                if current_session is None:
                    current_session = session_manager.get_active_session_id()

                # ② 프레임 디코딩 + 녹화를 백그라운드 스레드에서 실행 (이벤트 루프 논블로킹)
                if current_session is not None:
                    asyncio.get_running_loop().run_in_executor(
                        _frame_executor,
                        _sync_process_frame, session_manager, current_session, payload,
                    )

                # ③ 주기적 파지 확률 추론 → 별도 스레드에서 실행
                if (current_session
                        and now - last_infer_time >= infer_interval
                        and not infer_state["running"]):
                    last_infer_time = now
                    infer_state["running"] = True
                    asyncio.create_task(
                        _run_inference(
                            session_manager, current_session,
                            relay_hub, infer_state,
                        )
                    )

        except WebSocketDisconnect:
            pass
        finally:
            if current_session is not None:
                await session_manager.stop(current_session)
            print(f"[ws_rpi] disconnected")

    return router


async def _run_inference(
    session_manager: SessionManager,
    session_id: str,
    relay_hub: RelayHub,
    infer_state: dict,
) -> None:
    try:
        t0 = time.monotonic()
        grasp = await asyncio.to_thread(
            _sync_infer_grasp, session_manager, session_id
        )
        elapsed = (time.monotonic() - t0) * 1000
        if grasp:
            print(f"[ws_rpi] inference {elapsed:.0f}ms conf={grasp['confidence']:.3f}")
            # ThreeJawGraspService는 이미 GRASP_POSE 형식으로 반환
            if grasp.get("event") == "GRASP_POSE":
                await relay_hub.broadcast_text(json.dumps(grasp).encode())
            else:
                score_data = {
                    "event": "GRASP_SCORE",
                    "confidence": grasp["confidence"],
                    "center_px": grasp["center_px"],
                    "width_px": grasp.get("width_px", 0.0),
                }
                if "detections" in grasp:
                    score_data["detections"] = grasp["detections"]
                await relay_hub.broadcast_text(json.dumps(score_data).encode())
    except Exception as e:
        print(f"[ws_rpi] inference error: {e}")
    finally:
        infer_state["running"] = False


async def _apply_control(
    text: str,
    session_manager: SessionManager,
    relay_hub: RelayHub,
    current_session: Optional[str],
) -> Optional[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"[ws_rpi] invalid control msg: {text!r}")
        return current_session

    event = data.get("event")
    session_id = data.get("session_id")

    if event == "START" and session_id:
        await session_manager.start(session_id)
        await relay_hub.broadcast_text(json.dumps({
            "event": "SESSION_START",
            "session_id": session_id,
        }).encode())
        return session_id

    if event == "STOP" and session_id:
        result = await session_manager.stop(session_id)
        judge = session_manager.last_judge_result
        await relay_hub.broadcast_text(json.dumps({
            "event": "GAME_RESULT",
            "session_id": session_id,
            "is_caught": judge.is_caught if judge else False,
            "confidence": judge.confidence if judge else 0.0,
        }).encode())
        return None

    # 사용자가 POST_GAME 에서 파란 버튼을 눌러 세션을 명시적으로 종료한 경우.
    # 5판 미만이어도 즉시 QR 안내 화면으로 전환하도록 브라우저에 릴레이.
    if event == "SESSION_END":
        # ws_browser 의 REQUEST_START 로 시작된 세션이라면 RPi 는 그 id 를 모르므로
        # SessionManager 에서 active id 를 가져와 정리. 영상 업로드까지 처리.
        active_id = current_session or session_manager.get_active_session_id()
        if active_id is not None:
            await session_manager.stop(active_id)
        await relay_hub.broadcast_text(json.dumps({
            "event": "SESSION_END",
        }).encode())
        return None

    # 그 외 단발성 UI 이벤트 (GUIDE / JOY_LEFT / JOY_RIGHT / BACK_TO_HOME /
    # ROUND_TIMER_START / PLAYING_IDLE_TIMEOUT 등) 는 그대로 브라우저로 forward.
    # 새 이벤트 추가 시 ws_rpi 코드 안 건드려도 자동 전달됨.
    if isinstance(event, str) and event:
        await relay_hub.broadcast_text(text.encode())
        return current_session

    print(f"[ws_rpi] unknown control: {data}")
    return current_session


async def _relay_without_depth(relay_hub: RelayHub, payload_bytes: bytes) -> None:
    try:
        # raw=True 로 unpack 하면 string key 가 bytes 로 변환되어 브라우저의
        # @msgpack/msgpack decode 결과에서 payload.color_2d 같은 접근이 깨진다.
        # → key 만 다시 string 으로 변환 후 packb 한다. JPEG bytes(value) 는 그대로 유지.
        data = msgpack.unpackb(payload_bytes, raw=True)
        if isinstance(data, dict):
            normalized = {
                (k.decode() if isinstance(k, (bytes, bytearray)) else k): v
                for k, v in data.items()
            }
            normalized.pop("depth_3d", None)
            normalized.pop("depth_3d_shape", None)
            lean_payload = msgpack.packb(normalized)
            await relay_hub.broadcast(lean_payload)
        else:
            await relay_hub.broadcast(payload_bytes)
    except Exception as e:
        print(f"[ws_rpi] failed to strip depth: {e}")
        await relay_hub.broadcast(payload_bytes)
