from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from services.ws_manager import manager
from services.auth_service import decode_token

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    # Validate JWT passed as a query param (browsers can't set headers on WS handshake).
    if token:
        try:
            decode_token(token)
        except Exception:
            await websocket.close(code=4401)
            return
    else:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket)
    try:
        while True:
            # We don't expect inbound client messages, but keep the loop alive
            # to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
