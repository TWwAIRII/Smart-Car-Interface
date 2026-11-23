from typing import Dict, List
from fastapi import WebSocket
from app.core.metrics import ACTIVE_WEBSOCKET_CONNECTIONS


class ConnectionManager:
    def __init__(self):
        # Klucz: vehicle_id -> lista połączonych klientów WebSocket
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, vehicle_id: int, websocket: WebSocket):
        await websocket.accept()
        if vehicle_id not in self.active_connections:
            self.active_connections[vehicle_id] = []
        self.active_connections[vehicle_id].append(websocket)
        ACTIVE_WEBSOCKET_CONNECTIONS.inc()

    def disconnect(self, vehicle_id: int, websocket: WebSocket):
        if vehicle_id in self.active_connections:
            if websocket in self.active_connections[vehicle_id]:
                self.active_connections[vehicle_id].remove(websocket)
                ACTIVE_WEBSOCKET_CONNECTIONS.dec()

    async def broadcast_to_vehicle(self, vehicle_id: int, payload: dict):
        if vehicle_id not in self.active_connections:
            return
        dead_connections = []
        for connection in self.active_connections[vehicle_id]:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(vehicle_id, dead)


ws_manager = ConnectionManager()
