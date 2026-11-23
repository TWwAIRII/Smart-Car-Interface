from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text, ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="driver", nullable=False)  # 'admin', 'driver', 'guest'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), unique=True, nullable=False, index=True)
    make = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    year = Column(Integer, nullable=False)

    # Rozszerzenia pod zamek centralny oraz parametry baku (Opel Corsa B = 46L)
    is_locked = Column(Boolean, default=True, nullable=False)
    fuel_tank_capacity_l = Column(Numeric(5, 2), default=46.00, nullable=False)
    base_avg_consumption = Column(Numeric(4, 2), default=6.40, nullable=False)

    telemetry_logs = relationship("VehicleTelemetry", back_populates="vehicle", cascade="all, delete-orphan")
    climate_setting = relationship("ClimateSettings", back_populates="vehicle", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="vehicle", cascade="all, delete-orphan")
    locations = relationship("VehicleLocation", back_populates="vehicle", cascade="all, delete-orphan")
    trips = relationship("Trip", back_populates="vehicle", cascade="all, delete-orphan")
    obd_errors = relationship("ObdError", back_populates="vehicle", cascade="all, delete-orphan")


class VehicleTelemetry(Base):
    __tablename__ = "vehicle_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    speed = Column(Integer, default=0, nullable=False)
    fuel_level = Column(Numeric(5, 2), nullable=False)            # % w baku (0-100)
    tire_pressure_psi = Column(Numeric(4, 1), nullable=False)     # PSI
    estimated_range_km = Column(Integer, nullable=False)          # Wyliczany zasięg w km
    current_interior_temp = Column(Numeric(4, 1), nullable=False) # Temp. w kabinie (°C)
    current_exterior_temp = Column(Numeric(4, 1), default=12.0, nullable=False) # Temp. zewnętrzna (°C)
    battery_voltage = Column(Numeric(4, 2), default=12.60, nullable=False)      # Napięcie akumulatora (V)
    engine_rpm = Column(Integer, default=0, nullable=False)       # Obroty silnika (RPM)
    updated_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    vehicle = relationship("Vehicle", back_populates="telemetry_logs")


class ClimateSettings(Base):
    __tablename__ = "climate_settings"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), unique=True, nullable=False)
    target_temperature = Column(Numeric(4, 1), default=21.0, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    webasto_active = Column(Boolean, default=False, nullable=False)  # Ogrzewanie postojowe Webasto
    fan_speed = Column(Integer, default=0, nullable=False)           # Bieg wentylatora nawiewu (0-4)
    scheduled_time = Column(String(16), nullable=True)               # Np. "07:30"
    updated_at = Column(DateTime(timezone=True), default=utc_now)

    vehicle = relationship("Vehicle", back_populates="climate_setting")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # np. LOW_FUEL, TIRE_PRESSURE, OBD_ERROR, SECURITY, WEBASTO
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    vehicle = relationship("Vehicle", back_populates="notifications")


class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    vehicle = relationship("Vehicle", back_populates="locations")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    start_location = Column(String(120), nullable=False)
    end_location = Column(String(120), nullable=True)
    distance_km = Column(Numeric(7, 2), default=0.0, nullable=False)
    avg_consumption = Column(Numeric(4, 2), default=0.0, nullable=False)
    ecodriving_score = Column(Integer, default=100, nullable=False)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    vehicle = relationship("Vehicle", back_populates="trips")


class ObdError(Base):
    __tablename__ = "obd_errors"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(16), nullable=False)        # Np. P0170, P0400
    description = Column(String(255), nullable=False)
    severity = Column(String(20), default="warning", nullable=False)  # 'warning' | 'critical'
    is_active = Column(Boolean, default=True, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=utc_now)
    vehicle = relationship("Vehicle", back_populates="obd_errors")
    

