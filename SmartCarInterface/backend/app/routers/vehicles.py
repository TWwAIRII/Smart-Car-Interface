from typing import List, Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db, SessionLocal
from app.core.security import (
    get_current_user,
    require_driver_or_admin,
    require_admin,
    get_user_from_token_str,
)
from app.core.ws_manager import ws_manager
from app.models.entities import (
    User,
    VehicleTelemetry,
    Notification,
    VehicleLocation,
    Trip,
    ObdError,
)
from app.schemas.dto import (
    VehicleCreateRequest,
    VehicleUpdateRequest,
    VehicleResponse,
    VehicleDashboardResponse,
    TelemetryIngestRequest,
    TelemetryResponse,
    ClimateUpdateRequest,
    ClimateResponse,
    LockUpdateRequest,
    ObdErrorCreateRequest,
    ObdErrorResponse,
    NotificationResponse,
    LocationResponse,
    TripStartRequest,
    TripEndRequest,
    TripResponse,
)
from app.services.vehicle_service import VehicleBusinessService

router = APIRouter(prefix="/api/vehicles", tags=["Pojazd, Telemetria i Sterowanie"])


# ==================== CRUD GŁÓWNEGO ZASOBU: VEHICLES ====================

@router.get("", response_model=List[VehicleResponse], status_code=status.HTTP_200_OK)
def list_vehicles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera listę wszystkich zarejestrowanych pojazdów."""
    return VehicleBusinessService.list_vehicles(db)


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: VehicleCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[JWT: admin] Dodaje nowy pojazd do systemu (201 Created lub 409 Conflict)."""
    return VehicleBusinessService.create_vehicle(db, payload)


@router.get("/{vehicle_id}", response_model=VehicleResponse, status_code=status.HTTP_200_OK)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera podstawowe dane pojedynczego pojazdu."""
    return VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)


@router.put("/{vehicle_id}", response_model=VehicleResponse, status_code=status.HTTP_200_OK)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[JWT: admin] Aktualizuje dane pojazdu."""
    return VehicleBusinessService.update_vehicle(db, vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[JWT: admin] Usuwa pojazd wraz z powiązanymi rekordami (204 No Content)."""
    VehicleBusinessService.delete_vehicle(db, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== DASHBOARD, TELEMETRIA I STEROWANIE ====================

@router.get("/{vehicle_id}/dashboard", response_model=VehicleDashboardResponse, status_code=status.HTTP_200_OK)
def get_vehicle_dashboard(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    [JWT: admin/driver/guest] Zwraca kompletny stan pojazdu: ostatnią telemetrię,
    ustawienia Webasto/nawiewu, stan zamka centralnego, błędy OBD-II, powiadomienia oraz kamery.
    """
    vehicle = VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)

    latest_telemetry = (
        db.query(VehicleTelemetry)
        .filter(VehicleTelemetry.vehicle_id == vehicle_id)
        .order_by(desc(VehicleTelemetry.updated_at))
        .first()
    )
    latest_location = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(desc(VehicleLocation.recorded_at))
        .first()
    )
    active_obd = (
        db.query(ObdError)
        .filter(ObdError.vehicle_id == vehicle_id, ObdError.is_active.is_(True))
        .order_by(desc(ObdError.detected_at))
        .all()
    )
    unread_notifs = (
        db.query(Notification)
        .filter(Notification.vehicle_id == vehicle_id, Notification.is_read.is_(False))
        .order_by(desc(Notification.created_at))
        .limit(15)
        .all()
    )

    return {
        "id": vehicle.id,
        "vin": vehicle.vin,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "is_locked": vehicle.is_locked,
        "latest_telemetry": latest_telemetry,
        "climate": vehicle.climate_setting,
        "active_obd_errors": active_obd,
        "unread_notifications": unread_notifs,
        "latest_location": latest_location,
        "camera_streams": {
            "front_camera_mp4": "/media/front_camera.mp4",
            "rear_camera_mp4": "/media/rear_camera.mp4",
        },
    }


@router.post("/{vehicle_id}/telemetry", response_model=TelemetryResponse, status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    vehicle_id: int,
    payload: TelemetryIngestRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """
    [JWT: driver/admin] Zapisuje nową paczkę telemetrii z modułu pojazdu / symulatora (201 Created)
    i natychmiast rozsyła zaktualizowany stan przez WebSocket.
    """
    telemetry, new_notifs = VehicleBusinessService.process_incoming_telemetry(db, vehicle_id, payload)
    vehicle = VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)

    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {
            "event": "TELEMETRY_UPDATE",
            "vehicle_id": vehicle_id,
            "is_locked": vehicle.is_locked,
            "telemetry": {
                "speed": telemetry.speed,
                "fuel_level": float(telemetry.fuel_level),
                "tire_pressure_psi": float(telemetry.tire_pressure_psi),
                "estimated_range_km": telemetry.estimated_range_km,
                "current_interior_temp": float(telemetry.current_interior_temp),
                "current_exterior_temp": float(telemetry.current_exterior_temp),
                "battery_voltage": float(telemetry.battery_voltage),
                "engine_rpm": telemetry.engine_rpm,
                "updated_at": telemetry.updated_at.isoformat(),
            },
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "new_notifications": [
                {"id": n.id, "type": n.type, "message": n.message} for n in new_notifs
            ],
        },
    )
    return telemetry


@router.put("/{vehicle_id}/climate", response_model=ClimateResponse, status_code=status.HTTP_200_OK)
async def update_climate_and_webasto(
    vehicle_id: int,
    payload: ClimateUpdateRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Sterowanie ogrzewaniem postojowym Webasto, temperaturą docelową i nawiewem (0-4)."""
    climate = VehicleBusinessService.update_climate_settings(db, vehicle_id, payload)
    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {
            "event": "CLIMATE_CHANGE",
            "vehicle_id": vehicle_id,
            "climate": {
                "target_temperature": float(climate.target_temperature),
                "is_active": climate.is_active,
                "webasto_active": climate.webasto_active,
                "fan_speed": climate.fan_speed,
                "scheduled_time": climate.scheduled_time,
            },
        },
    )
    return climate


@router.post("/{vehicle_id}/lock", status_code=status.HTTP_200_OK)
async def control_central_lock(
    vehicle_id: int,
    payload: LockUpdateRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Zdalne otwieranie i zamykanie zamka centralnego."""
    vehicle = VehicleBusinessService.set_central_lock(db, vehicle_id, payload.is_locked)
    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {
            "event": "LOCK_STATE_CHANGE",
            "vehicle_id": vehicle_id,
            "is_locked": vehicle.is_locked,
        },
    )
    return {"vehicle_id": vehicle.id, "is_locked": vehicle.is_locked}


# ==================== DIAGNOSTYKA OBD-II ====================

@router.get("/{vehicle_id}/obd", response_model=List[ObdErrorResponse], status_code=status.HTTP_200_OK)
def get_obd_errors(
    vehicle_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera listę kodów błędów diagnostycznych OBD-II."""
    VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)
    query = db.query(ObdError).filter(ObdError.vehicle_id == vehicle_id)
    if active_only:
        query = query.filter(ObdError.is_active.is_(True))
    return query.order_by(desc(ObdError.detected_at)).all()


@router.post("/{vehicle_id}/obd", response_model=ObdErrorResponse, status_code=status.HTTP_201_CREATED)
async def report_obd_error(
    vehicle_id: int,
    payload: ObdErrorCreateRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Rejestruje nowy kod błędu OBD-II zgłoszony przez pojazd/symulator."""
    err = VehicleBusinessService.register_obd_error(db, vehicle_id, payload)
    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {
            "event": "OBD_ERROR_DETECTED",
            "vehicle_id": vehicle_id,
            "obd_error": {
                "id": err.id,
                "code": err.code,
                "description": err.description,
                "severity": err.severity,
            },
        },
    )
    return err


@router.delete("/{vehicle_id}/obd", status_code=status.HTTP_200_OK)
async def clear_obd_errors(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Kasuje aktywne kody błędów OBD-II w sterowniku pojazdu (tylko na postoju)."""
    cleared = VehicleBusinessService.clear_obd_errors(db, vehicle_id)
    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {"event": "OBD_ERRORS_CLEARED", "vehicle_id": vehicle_id, "cleared_count": cleared},
    )
    return {"vehicle_id": vehicle_id, "cleared_count": cleared}


# ==================== POWIADOMIENIA (NOTIFICATIONS) ====================

@router.get("/{vehicle_id}/notifications", response_model=List[NotificationResponse], status_code=status.HTTP_200_OK)
def get_notifications(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera historię powiadomień dla pojazdu."""
    VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)
    return (
        db.query(Notification)
        .filter(Notification.vehicle_id == vehicle_id)
        .order_by(desc(Notification.created_at))
        .limit(50)
        .all()
    )


@router.patch(
    "/{vehicle_id}/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
def mark_notification_read(
    vehicle_id: int,
    notification_id: int,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Oznacza wskazane powiadomienie jako przeczytane."""
    return VehicleBusinessService.mark_notification_read(db, vehicle_id, notification_id)


@router.delete(
    "/{vehicle_id}/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notification(
    vehicle_id: int,
    notification_id: int,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Usuwa powiadomienie (204 No Content)."""
    VehicleBusinessService.delete_notification(db, vehicle_id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== LOKALIZACJE I TRASY (LOCATIONS & TRIPS) ====================

@router.get("/{vehicle_id}/locations", response_model=List[LocationResponse], status_code=status.HTTP_200_OK)
def get_location_history(
    vehicle_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera historię pozycji GPS pojazdu."""
    VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)
    return (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(desc(VehicleLocation.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/{vehicle_id}/trips", response_model=List[TripResponse], status_code=status.HTTP_200_OK)
def get_trips(
    vehicle_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """[JWT: admin/driver/guest] Pobiera listę tras pojazdu."""
    VehicleBusinessService.get_vehicle_or_404(db, vehicle_id)
    return (
        db.query(Trip)
        .filter(Trip.vehicle_id == vehicle_id)
        .order_by(desc(Trip.started_at))
        .all()
    )


@router.post("/{vehicle_id}/trips/start", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def start_vehicle_trip(
    vehicle_id: int,
    payload: TripStartRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Rozpoczyna nową trasę pojazdu (201 Created)."""
    return VehicleBusinessService.start_trip(db, vehicle_id, payload)


@router.post("/{vehicle_id}/trips/{trip_id}/end", response_model=TripResponse, status_code=status.HTTP_200_OK)
def end_vehicle_trip(
    vehicle_id: int,
    trip_id: int,
    payload: TripEndRequest,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Kończy trasę i wylicza ocenę Ecodrivingu."""
    return VehicleBusinessService.end_trip(db, vehicle_id, trip_id, payload)


@router.delete("/{vehicle_id}/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle_trip(
    vehicle_id: int,
    trip_id: int,
    db: Session = Depends(get_db),
    _operator: User = Depends(require_driver_or_admin),
):
    """[JWT: driver/admin] Usuwa zapisaną trasę (204 No Content)."""
    VehicleBusinessService.delete_trip(db, vehicle_id, trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== WEBSOCKET (CHRONIONY TOKENEM JWT) ====================

@router.websocket("/ws/{vehicle_id}")
async def vehicle_telemetry_websocket(
    websocket: WebSocket,
    vehicle_id: int,
    token: Optional[str] = Query(None),
):
    """
    [JWT] Kanał WebSocket do odświeżania Dashboardu w czasie rzeczywistym.
    Wymaga przekazania tokenu JWT jako parametr `?token=<JWT>` lub w nagłówku `Authorization: Bearer <JWT>`.
    """
    raw_token = token
    if not raw_token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

    db = SessionLocal()
    try:
        user = get_user_from_token_str(raw_token, db)
    finally:
        db.close()

    if not user:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Wymagana autoryzacja JWT (?token=<JWT>)",
        )
        return

    await ws_manager.connect(vehicle_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "PING":
                await websocket.send_json({"event": "PONG", "vehicle_id": vehicle_id})
    except WebSocketDisconnect:
        ws_manager.disconnect(vehicle_id, websocket)
