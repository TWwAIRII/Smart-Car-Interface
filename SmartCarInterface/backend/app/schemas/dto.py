from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# --- USERS & AUTH ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserStatusUpdate(BaseModel):
    is_active: bool
    role: Optional[str] = Field(None, pattern="^(admin|driver|guest)$")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- TELEMETRY ---
class TelemetryIngestRequest(BaseModel):
    speed: int = Field(..., ge=0, le=260)
    fuel_level: float = Field(..., ge=0.0, le=100.0)
    tire_pressure_psi: float = Field(..., ge=0.0, le=60.0)
    current_interior_temp: float = Field(..., ge=-40.0, le=70.0)
    current_exterior_temp: float = Field(12.0, ge=-45.0, le=60.0)
    battery_voltage: float = Field(12.6, ge=8.0, le=16.0)
    engine_rpm: int = Field(0, ge=0, le=8000)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class TelemetryResponse(BaseModel):
    id: int
    vehicle_id: int
    speed: int
    fuel_level: float
    tire_pressure_psi: float
    estimated_range_km: int
    current_interior_temp: float
    current_exterior_temp: float
    battery_voltage: float
    engine_rpm: int
    updated_at: datetime

    class Config:
        from_attributes = True


# --- CLIMATE & WEBASTO ---
class ClimateUpdateRequest(BaseModel):
    target_temperature: float = Field(..., ge=15.0, le=30.0)
    is_active: bool
    webasto_active: bool = False
    fan_speed: int = Field(0, ge=0, le=4)
    scheduled_time: Optional[str] = None


class ClimateResponse(BaseModel):
    vehicle_id: int
    target_temperature: float
    is_active: bool
    webasto_active: bool
    fan_speed: int
    scheduled_time: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


# --- CENTRAL LOCK ---
class LockUpdateRequest(BaseModel):
    is_locked: bool


# --- OBD-II DIAGNOSTICS ---
class ObdErrorCreateRequest(BaseModel):
    code: str = Field(..., example="P0170")
    description: str = Field(..., example="Nieprawidłowy skład mieszanki paliwowo-powietrznej (Bank 1)")
    severity: str = Field("warning", pattern="^(warning|critical)$")


class ObdErrorResponse(BaseModel):
    id: int
    vehicle_id: int
    code: str
    description: str
    severity: str
    is_active: bool
    detected_at: datetime

    class Config:
        from_attributes = True


# --- NOTIFICATIONS ---
class NotificationResponse(BaseModel):
    id: int
    vehicle_id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- LOCATIONS & TRIPS ---
class LocationResponse(BaseModel):
    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    recorded_at: datetime

    class Config:
        from_attributes = True


class TripStartRequest(BaseModel):
    start_location: str = Field(..., example="Kraków, ul. Warszawska 24")


class TripEndRequest(BaseModel):
    end_location: str = Field(..., example="Tarnów, Rynek 1")
    distance_km: float = Field(..., gt=0.1)


class TripResponse(BaseModel):
    id: int
    vehicle_id: int
    start_location: str
    end_location: Optional[str]
    distance_km: float
    avg_consumption: float
    ecodriving_score: int
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- COMPLETE DASHBOARD SNAPSHOT ---
class VehicleDashboardResponse(BaseModel):
    id: int
    vin: str
    make: str
    model: str
    year: int
    is_locked: bool
    latest_telemetry: Optional[TelemetryResponse]
    climate: Optional[ClimateResponse]
    active_obd_errors: List[ObdErrorResponse]
    unread_notifications: List[NotificationResponse]
    latest_location: Optional[LocationResponse]
    camera_streams: dict
