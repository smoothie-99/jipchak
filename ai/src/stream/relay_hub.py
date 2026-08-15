import asyncio
import time
from typing import Dict, Optional

from fastapi import WebSocket


class ClientChannel:
    """
    한 브라우저 client 별 전용 채널.

    핵심 — **latest frame only** 정책:
      - producer (broadcast) 는 `offer(payload)` 로 최신 payload 만 슬롯에 덮어씀.
      - consumer (worker coroutine) 는 슬롯에서 가장 최근 frame 을 꺼내 ws.send_bytes.
      - 한 client 의 네트워크가 느려도 옛 frame 은 자동 drop → latency 누적 안 됨.
    """

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self._slot: Optional[bytes] = None
        self._event = asyncio.Event()
        self._alive = True
        self._worker_task: Optional[asyncio.Task] = None

    def offer(self, payload: bytes) -> None:
        """Producer 가 호출. 옛 frame 은 덮어써짐 (drop)."""
        self._slot = payload
        self._event.set()

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        self._alive = False
        self._event.set()
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=1.0)
            except (asyncio.TimeoutError, Exception):
                self._worker_task.cancel()

    @property
    def alive(self) -> bool:
        return self._alive

    # 균일한 frame 도착 보장 (10 fps cap). 너무 자주 보내면 client 처리 jitter,
    # 너무 드물면 끊김 — 100ms 가 시각적으로 부드러우면서 latency 누적 최소.
    _MIN_SEND_INTERVAL_S = 0.1

    async def _worker(self) -> None:
        """소비자 루프 — 슬롯의 latest payload 를 균일 fps 로 send."""
        last_send = 0.0
        try:
            while self._alive:
                await self._event.wait()
                self._event.clear()
                payload = self._slot
                self._slot = None
                if payload is None:
                    continue

                # rate limit: 마지막 send 후 일정 시간 지났을 때만 보냄.
                # 더 빨리 도착한 frame 은 slot 에 덮여서 자연스럽게 drop.
                now = time.monotonic()
                elapsed = now - last_send
                if elapsed < self._MIN_SEND_INTERVAL_S:
                    await asyncio.sleep(self._MIN_SEND_INTERVAL_S - elapsed)
                    # 대기 동안 새 frame 들이 slot 에 덮였을 수 있음 — 최신 다시 읽기
                    if self._slot is not None:
                        payload = self._slot
                        self._slot = None

                try:
                    await self.ws.send_bytes(payload)
                    last_send = time.monotonic()
                except Exception:
                    self._alive = False
                    return
        except asyncio.CancelledError:
            return


class RelayHub:
    """
    RPi 영상을 브라우저 구독자들에게 fan-out.

    구조:
      - subscribe()/unsubscribe() 로 client 등록/해제
      - broadcast(payload) 는 각 client 의 channel.offer() 만 호출 (즉시 return)
      - 각 client 는 전용 worker 가 자기 속도로 latest frame 만 send
      - 한 client 가 느려도 다른 client 영향 X, latency 누적 X
    """

    def __init__(self) -> None:
        self._clients: Dict[WebSocket, ClientChannel] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._clients:
                return
            channel = ClientChannel(ws)
            self._clients[ws] = channel
        await channel.start()
        print(f"[RelayHub] subscribed (total={len(self._clients)})")

    async def unsubscribe(self, ws: WebSocket) -> None:
        async with self._lock:
            channel = self._clients.pop(ws, None)
        if channel is not None:
            await channel.stop()
        print(f"[RelayHub] unsubscribed (total={len(self._clients)})")

    async def broadcast(self, payload: bytes) -> None:
        """RPi 가 보낸 frame 을 모든 channel 에 offer (즉시 return).

        실제 네트워크 send 는 각 channel worker 가 비동기 처리. 옛 frame 은 자동 drop.
        """
        if not self._clients:
            return

        dead: list = []
        async with self._lock:
            channels = list(self._clients.items())
        for ws, channel in channels:
            if channel.alive:
                channel.offer(payload)
            else:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    ch = self._clients.pop(ws, None)
                    if ch is not None:
                        await ch.stop()
            print(f"[RelayHub] cleaned {len(dead)} dead client(s)")

    async def broadcast_text(self, data: bytes) -> None:
        """텍스트(JSON) 이벤트 — 영상 frame 보다 훨씬 작아 buffer 누적 위험 X.
        그래도 dead client 정리 위해 try/except 로 직접 send.
        """
        if not self._clients:
            return
        async with self._lock:
            targets = list(self._clients.keys())
        dead: list = []
        for ws in targets:
            try:
                await ws.send_text(data.decode())
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    ch = self._clients.pop(ws, None)
                    if ch is not None:
                        await ch.stop()

    @property
    def subscriber_count(self) -> int:
        return len(self._clients)
