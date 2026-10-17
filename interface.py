"""FastAPI web interface + WebSocket bridge. The API key never reaches the browser."""
import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

import config


class Hub:
    """Thread-safe fan-out of assistant events to every connected browser tab."""

    def __init__(self):
        self.clients = set()
        self.loop = None
        self.assistant = None

    def emit(self, event: dict) -> None:
        if self.loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self.loop)

    async def _broadcast(self, event: dict) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(event)
            except Exception:
                self.clients.discard(ws)


def create_app(hub: Hub) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        hub.loop = asyncio.get_running_loop()
        yield

    app = FastAPI(title="JARVIS", lifespan=lifespan, docs_url=None, redoc_url=None)
    allowed = {f"http://127.0.0.1:{config.PORT}", f"http://localhost:{config.PORT}"}

    @app.get("/")
    async def index():
        return FileResponse(config.BASE_DIR / "static" / "index.html")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        # Block other websites from driving the assistant through the user's browser.
        origin = ws.headers.get("origin")
        if origin is not None and origin not in allowed:
            await ws.close(code=1008)
            return
        await ws.accept()
        hub.clients.add(ws)
        try:
            for event in hub.assistant.snapshot():
                await ws.send_json(event)
            while True:
                msg = await ws.receive_json()
                kind = msg.get("type")
                if kind == "toggle_mic":
                    hub.assistant.toggle_mic()
                elif kind == "stop":
                    hub.assistant.emergency_stop()
                elif kind == "text" and str(msg.get("text", "")).strip():
                    threading.Thread(target=hub.assistant.handle_text,
                                     args=(str(msg["text"])[:2000],), daemon=True).start()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            hub.clients.discard(ws)

    return app
