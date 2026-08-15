import asyncio
import websockets
from websockets.exceptions import ConnectionClosed

from ..config import WS_URL, RECONNECT_INTERVAL

class WebSocketClient:
    """FastAPI 서버와의 WebSocket 통신을 관리하는 클래스"""
    def __init__(self):
        self.url = WS_URL
        self.connection = None
        self._is_running = False

    async def connect(self):
        """서버에 연결하고 연결을 유지합니다. 재연결 로직 포함."""
        self._is_running = True
        while self._is_running:
            try:
                print(f"[WebSocketClient] Connecting to {self.url}...")
                # ping/pong 등을 설정하여 연결 안정성을 높일 수 있습니다.
                async with websockets.connect(self.url, max_size=None) as ws:
                    self.connection = ws
                    print("[WebSocketClient] Connected successfully.")
                    
                    # 연결이 유지되는 동안 대기 (서버로부터 메시지를 받을 일이 있다면 여기서 수신)
                    # 현재는 송신 전용이므로 연결 유지 대기만 합니다.
                    while self._is_running and not ws.closed:
                        await asyncio.sleep(1)
                        
            except (ConnectionRefusedError, ConnectionClosed) as e:
                self.connection = None
                print(f"[WebSocketClient] Connection failed/closed: {e}. Reconnecting in {RECONNECT_INTERVAL}s...")
                await asyncio.sleep(RECONNECT_INTERVAL)
            except Exception as e:
                self.connection = None
                print(f"[WebSocketClient] Unexpected error: {e}. Reconnecting in {RECONNECT_INTERVAL}s...")
                await asyncio.sleep(RECONNECT_INTERVAL)

    async def send_binary(self, data: bytes) -> bool:
        """바이너리 데이터를 전송합니다."""
        if not self.connection or self.connection.closed:
            return False
            
        try:
            await self.connection.send(data)
            return True
        except ConnectionClosed:
            self.connection = None
            return False
        except Exception as e:
            print(f"[WebSocketClient] Send error: {e}")
            return False

    async def stop(self):
        """연결을 종료합니다."""
        self._is_running = False
        if self.connection and not self.connection.closed:
            await self.connection.close()
            print("[WebSocketClient] Connection closed by client.")
