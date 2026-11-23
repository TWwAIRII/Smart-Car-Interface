from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


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
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


# --- VEHICLES (CRUD) ---
class VehicleCreateRequest(BaseModel):
    vin: str = Field(..., min_length=5, max_length=17, examples=["W0L000073W4999999"])
    make: str = Field(..., min_length=1, max_length=64, examples=["Opel"])
    model: str = Field(..., min_length=1, max_length=64, examples=["Corsa B 1.2i"])
    year: int = Field(..., ge=1950, le=2100, examples=[1999])
    is_locked: bool = True
    fuel_tank_capacity_l: float = Field(46.0, gt=0.0, le=200.0)
    base_avg_consumption: float = Field(6.4, gt=0.5, le=40.0)


class VehicleUpdateRequest(BaseModel):
    vin: str = Field(..., min_length=5, max_length=17, examples=["W0L000073W4123456"])
    make: str = Field(..., min_length=1, max_length=64, examples=["Opel"])
    model: str = Field(..., min_length=1, max_length=64, examples=["Corsa B 1.4i 16V (Green Edition)"])
    year: int = Field(..., ge=1950, le=2100, examples=[1998])
    is_locked: bool = True
    fuel_tank_capacity_l: float = Field(46.0, gt=0.0, le=200.0)
    base_avg_consumption: float = Field(6.4, gt=0.5, le=40.0)


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vin: str
    make: str
    model: str
    year: int
    is_locked: bool
    fuel_tank_capacity_l: float
    base_avg_consumption: float


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
    model_config = ConfigDict(from_attributes=True)

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


# --- CLIMATE & WEBASTO ---
class ClimateUpdateRequest(BaseModel):
    target_temperature: float = Field(..., ge=15.0, le=30.0)
    is_active: bool
    webasto_active: bool = False
    fan_speed: int = Field(0, ge=0, le=4)
    scheduled_time: Optional[str] = None


class ClimateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: int
    target_temperature: float
    is_active: bool
    webasto_active: bool
    fan_speed: int
    scheduled_time: Optional[str]
    updated_at: datetime


# --- CENTRAL LOCK ---
class LockUpdateRequest(BaseModel):
    is_locked: bool


# --- OBD-II DIAGNOSTICS ---
class ObdErrorCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=16, examples=["P0170"])
    description: str = Field(
        ...,
        min_length=3,
        max_length=255,
        examples=["Nieprawidłowy skład mieszanki paliwowo-powietrznej (Bank 1)"],
    )
    severity: str = Field("warning", pattern="^(warning|critical)$")


class ObdErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    code: str
    description: str
    severity: str
    is_active: bool
    detected_at: datetime


# --- NOTIFICATIONS ---
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime


# --- LOCATIONS & TRIPS ---
class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    recorded_at: datetime


class TripStartRequest(BaseModel):
    start_location: str = Field(..., min_length=2, max_length=120, examples=["Kraków, ul. Warszawska 24"])


class TripEndRequest(BaseModel):
    end_location: str = Field(..., min_length=2, max_length=120, examples=["Tarnów, Rynek 1"])
    distance_km: float = Field(..., gt=0.1)


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    start_location: str
    end_location: Optional[str]
    distance_km: float
    avg_consumption: float
    ecodriving_score: int
    started_at: datetime
    ended_at: Optional[datetime]


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
