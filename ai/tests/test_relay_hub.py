import asyncio

import pytest

from src.stream.relay_hub import RelayHub


class FakeWebSocket:
    def __init__(self, fail_after: int | None = None) -> None:
        self.received: list[bytes] = []
        self.fail_after = fail_after  # N번째 send부터 실패

    async def send_bytes(self, payload: bytes) -> None:
        if self.fail_after is not None and len(self.received) >= self.fail_after:
            raise ConnectionError("simulated client gone")
        self.received.append(payload)


async def test_subscribe_and_broadcast_to_all_clients():
    hub = RelayHub()
    a, b = FakeWebSocket(), FakeWebSocket()
    await hub.subscribe(a)
    await hub.subscribe(b)

    await hub.broadcast(b"hello")

    assert a.received == [b"hello"]
    assert b.received == [b"hello"]
    assert hub.subscriber_count == 2


async def test_unsubscribe_stops_receiving():
    hub = RelayHub()
    a, b = FakeWebSocket(), FakeWebSocket()
    await hub.subscribe(a)
    await hub.subscribe(b)
    await hub.unsubscribe(a)

    await hub.broadcast(b"x")

    assert a.received == []
    assert b.received == [b"x"]
    assert hub.subscriber_count == 1


async def test_dead_client_is_auto_cleaned():
    hub = RelayHub()
    healthy = FakeWebSocket()
    dead = FakeWebSocket(fail_after=0)  # 첫 send부터 실패
    await hub.subscribe(healthy)
    await hub.subscribe(dead)

    await hub.broadcast(b"ping")

    # dead client는 자동 제거, healthy는 정상 수신
    assert hub.subscriber_count == 1
    assert healthy.received == [b"ping"]


async def test_broadcast_with_no_clients_is_noop():
    hub = RelayHub()
    await hub.broadcast(b"nobody")  # 예외 없이 통과해야 함
    assert hub.subscriber_count == 0
