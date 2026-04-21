import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import asyncio

from src.core.logger import setup_logger
from src.dashboard.routes import router as api_router
from src.dashboard.ws_manager import manager

log = setup_logger("dashboard")

app = FastAPI(title="Sentinel AI Dashboard")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
async def on_startup():
    # Keep a reference to uvicorn's event loop for cross-thread broadcasts.
    manager.set_loop(asyncio.get_running_loop())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We don't expect messages from client currently, but if we get one, just ack
            pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Mount static files after websocket route registration.
# A root mount can otherwise shadow /ws and cause websocket handshake failures.
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

def run_server(host="0.0.0.0", port=8000):
    """Run the FastAPI server."""
    display_host = "localhost" if host in ("0.0.0.0", "::") else host
    log.info(f"Starting Sentinel AI Dashboard on http://{display_host}:{port}")
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # Disable signal handlers because they crash when running in a background thread
    server.install_signal_handlers = lambda: None
    server.run()

if __name__ == "__main__":
    run_server()
