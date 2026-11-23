from typing import List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.ws_manager import ws_manager
from app.models.entities import (
    VehicleTelemetry,
    Notification,
    VehicleLocation,
    Trip,
    ObdError,
)
from app.schemas.dto import (
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


@router.get("/{vehicle_id}/dashboard", response_model=VehicleDashboardResponse)
def get_vehicle_dashboard(vehicle_id: int, db: Session = Depends(get_db)):
    """
    [Dashboard] Zwraca kompletny stan pojazdu: ostatnią telemetrię, ustawienia Webasto/nawiewu,
    stan zamka centralnego, aktywne błędy OBD-II, nieprzeczytane powiadomienia oraz linki do kamer.
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
            "front_camera_mp4": f"/media/front_camera.mp4",
            "rear_camera_mp4": f"/media/rear_camera.mp4",
        },
    }


@router.post("/{vehicle_id}/telemetry", response_model=TelemetryResponse)
async def ingest_telemetry(
    vehicle_id: int,
    payload: TelemetryIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Odbiera nową paczkę telemetrii z modułu pojazdu / symulatora, przelicza zasięg
    i natychmiast rozsyła zaktualizowany stan przez WebSocket do podłączonych klientów.
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


@router.put("/{vehicle_id}/climate", response_model=ClimateResponse)
async def update_climate_and_webasto(
    vehicle_id: int,
    payload: ClimateUpdateRequest,
    db: Session = Depends(get_db),
):
    """[Zarządzanie] Sterowanie ogrzewaniem postojowym Webasto, temperaturą docelową i nawiewem (0-4)."""
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


@router.post("/{vehicle_id}/lock")
async def control_central_lock(
    vehicle_id: int,
    payload: LockUpdateRequest,
    db: Session = Depends(get_db),
):
    """[Zarządzanie] Zdalne otwieranie i zamykanie zamka centralnego."""
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


@router.get("/{vehicle_id}/obd", response_model=List[ObdErrorResponse])
def get_obd_errors(vehicle_id: int, active_only: bool = True, db: Session = Depends(get_db)):
    """Pobiera listę kodów błędów diagnostycznych z komputera OBD-II."""
    query = db.query(ObdError).filter(ObdError.vehicle_id == vehicle_id)
    if active_only:
        query = query.filter(ObdError.is_active.is_(True))
    return query.order_by(desc(ObdError.detected_at)).all()


@router.post("/{vehicle_id}/obd", response_model=ObdErrorResponse)
async def report_obd_error(
    vehicle_id: int,
    payload: ObdErrorCreateRequest,
    db: Session = Depends(get_db),
):
    """Rejestruje nowy kod błędu OBD-II zgłoszony przez pojazd/symulator."""
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


@router.delete("/{vehicle_id}/obd")
async def clear_obd_errors(vehicle_id: int, db: Session = Depends(get_db)):
    """[Zarządzanie] Kasuje aktywne kody błędów OBD-II w sterowniku pojazdu."""
    cleared = VehicleBusinessService.clear_obd_errors(db, vehicle_id)
    await ws_manager.broadcast_to_vehicle(
        vehicle_id,
        {"event": "OBD_ERRORS_CLEARED", "vehicle_id": vehicle_id, "cleared_count": cleared},
    )
    return {"vehicle_id": vehicle_id, "cleared_count": cleared}


@router.get("/{vehicle_id}/notifications", response_model=List[NotificationResponse])
def get_notifications(vehicle_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .filter(Notification.vehicle_id == vehicle_id)
        .order_by(desc(Notification.created_at))
        .limit(50)
        .all()
    )


@router.patch("/{vehicle_id}/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(vehicle_id: int, notification_id: int, db: Session = Depends(get_db)):
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.vehicle_id == vehicle_id)
        .first()
    )
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif


@router.get("/{vehicle_id}/locations", response_model=List[LocationResponse])
def get_location_history(vehicle_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(desc(VehicleLocation.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/{vehicle_id}/trips", response_model=List[TripResponse])
def get_trips(vehicle_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Trip)
        .filter(Trip.vehicle_id == vehicle_id)
        .order_by(desc(Trip.started_at))
        .all()
    )


@router.post("/{vehicle_id}/trips/start", response_model=TripResponse)
def start_vehicle_trip(vehicle_id: int, payload: TripStartRequest, db: Session = Depends(get_db)):
    return VehicleBusinessService.start_trip(db, vehicle_id, payload)


@router.post("/{vehicle_id}/trips/{trip_id}/end", response_model=TripResponse)
def end_vehicle_trip(
    vehicle_id: int,
    trip_id: int,
    payload: TripEndRequest,
    db: Session = Depends(get_db),
):
    return VehicleBusinessService.end_trip(db, vehicle_id, trip_id, payload)


@router.websocket("/ws/{vehicle_id}")
async def vehicle_telemetry_websocket(websocket: WebSocket, vehicle_id: int):
    """
    Kanał WebSocket do odświeżania Dashboardu w czasie rzeczywistym
    oraz dwukierunkowej komunikacji z symulatorem pojazdu.
    """
    await ws_manager.connect(vehicle_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Pozwala również na przesyłanie pingów lub komend przez WS
            if data.get("action") == "PING":
                await websocket.send_json({"event": "PONG", "vehicle_id": vehicle_id})
    except WebSocketDisconnect:
        ws_manager.disconnect(vehicle_id, websocket)
