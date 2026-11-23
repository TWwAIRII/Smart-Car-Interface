from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import (
    Vehicle,
    VehicleTelemetry,
    ClimateSettings,
    Notification,
    VehicleLocation,
    Trip,
    ObdError,
)
from app.schemas.dto import (
    VehicleCreateRequest,
    VehicleUpdateRequest,
    TelemetryIngestRequest,
    ClimateUpdateRequest,
    ObdErrorCreateRequest,
    TripStartRequest,
    TripEndRequest,
)
from app.core.metrics import (
    TELEMETRY_PACKETS_TOTAL,
    VEHICLE_SPEED_GAUGE,
    VEHICLE_FUEL_GAUGE,
    VEHICLE_INTERIOR_TEMP_GAUGE,
    VEHICLE_OBD_ERRORS_GAUGE,
)


class VehicleBusinessService:
    """
    Główna logika biznesowa systemu SmartCarInterface (Connected Car).
    Odpowiada za operacje CRUD na pojazdach, przeliczanie zasięgu, reguły bezpieczeństwa Webasto,
    diagnostykę OBD-II, ocenę stylu jazdy (Ecodriving) oraz zarządzanie powiadomieniami.
    """

    @staticmethod
    def list_vehicles(db: Session) -> List[Vehicle]:
        return db.query(Vehicle).order_by(Vehicle.id.asc()).all()

    @staticmethod
    def get_vehicle_or_404(db: Session, vehicle_id: int) -> Vehicle:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pojazd o ID={vehicle_id} nie istnieje.",
            )
        return vehicle

    @classmethod
    def create_vehicle(cls, db: Session, payload: VehicleCreateRequest) -> Vehicle:
        existing_vin = db.query(Vehicle).filter(Vehicle.vin == payload.vin).first()
        if existing_vin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Pojazd o numerze VIN '{payload.vin}' już istnieje w systemie.",
            )

        vehicle = Vehicle(
            vin=payload.vin,
            make=payload.make,
            model=payload.model,
            year=payload.year,
            is_locked=payload.is_locked,
            fuel_tank_capacity_l=payload.fuel_tank_capacity_l,
            base_avg_consumption=payload.base_avg_consumption,
        )
        db.add(vehicle)
        db.flush()

        # Domyślne ustawienia klimatyzacji/Webasto dla nowo utworzonego pojazdu
        db.add(
            ClimateSettings(
                vehicle_id=vehicle.id,
                target_temperature=21.0,
                is_active=False,
                webasto_active=False,
                fan_speed=0,
            )
        )
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @classmethod
    def update_vehicle(
        cls,
        db: Session,
        vehicle_id: int,
        payload: VehicleUpdateRequest,
    ) -> Vehicle:
        vehicle = cls.get_vehicle_or_404(db, vehicle_id)

        vin_conflict = (
            db.query(Vehicle)
            .filter(Vehicle.vin == payload.vin, Vehicle.id != vehicle_id)
            .first()
        )
        if vin_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Numer VIN '{payload.vin}' jest już przypisany do innego pojazdu.",
            )

        vehicle.vin = payload.vin
        vehicle.make = payload.make
        vehicle.model = payload.model
        vehicle.year = payload.year
        vehicle.is_locked = payload.is_locked
        vehicle.fuel_tank_capacity_l = payload.fuel_tank_capacity_l
        vehicle.base_avg_consumption = payload.base_avg_consumption

        db.commit()
        db.refresh(vehicle)
        return vehicle

    @classmethod
    def delete_vehicle(cls, db: Session, vehicle_id: int) -> None:
        vehicle = cls.get_vehicle_or_404(db, vehicle_id)
        db.delete(vehicle)
        db.commit()

    @staticmethod
    def calculate_estimated_range_km(
        vehicle: Vehicle,
        fuel_level_pct: float,
        webasto_active: bool = False,
        current_speed: int = 0,
    ) -> int:
        tank_capacity = float(vehicle.fuel_tank_capacity_l or 46.0)
        base_consumption = float(vehicle.base_avg_consumption or 6.4)
        remaining_liters = (fuel_level_pct / 100.0) * tank_capacity

        effective_consumption = base_consumption
        if webasto_active:
            effective_consumption += 0.35
        if current_speed > 110:
            effective_consumption += (current_speed - 110) * 0.04

        if effective_consumption <= 0:
            return 0

        estimated_km = int(round((remaining_liters / effective_consumption) * 100.0))
        return max(0, estimated_km)

    @staticmethod
    def _create_notification_if_not_recent(
        db: Session,
        vehicle_id: int,
        notif_type: str,
        message: str,
    ) -> Notification | None:
        existing = (
            db.query(Notification)
            .filter(
                Notification.vehicle_id == vehicle_id,
                Notification.type == notif_type,
                Notification.is_read.is_(False),
            )
            .first()
        )
        if existing:
            return None

        notif = Notification(
            vehicle_id=vehicle_id,
            type=notif_type,
            message=message,
            is_read=False,
        )
        db.add(notif)
        return notif

    @classmethod
    def process_incoming_telemetry(
        cls,
        db: Session,
        vehicle_id: int,
        payload: TelemetryIngestRequest,
    ) -> tuple[VehicleTelemetry, list[Notification]]:
        vehicle = cls.get_vehicle_or_404(db, vehicle_id)
        climate = vehicle.climate_setting
        webasto_on = bool(climate and climate.webasto_active)

        estimated_range = cls.calculate_estimated_range_km(
            vehicle=vehicle,
            fuel_level_pct=payload.fuel_level,
            webasto_active=webasto_on,
            current_speed=payload.speed,
        )

        telemetry = VehicleTelemetry(
            vehicle_id=vehicle_id,
            speed=payload.speed,
            fuel_level=payload.fuel_level,
            tire_pressure_psi=payload.tire_pressure_psi,
            estimated_range_km=estimated_range,
            current_interior_temp=payload.current_interior_temp,
            current_exterior_temp=payload.current_exterior_temp,
            battery_voltage=payload.battery_voltage,
            engine_rpm=payload.engine_rpm,
        )
        db.add(telemetry)

        if payload.latitude is not None and payload.longitude is not None:
            db.add(
                VehicleLocation(
                    vehicle_id=vehicle_id,
                    latitude=payload.latitude,
                    longitude=payload.longitude,
                )
            )

        generated_notifications: list[Notification] = []

        if payload.fuel_level < 15.0:
            notif = cls._create_notification_if_not_recent(
                db,
                vehicle_id,
                "LOW_FUEL",
                f"Niski poziom paliwa ({payload.fuel_level:.1f}%). Szacowany zasięg: {estimated_range} km.",
            )
            if notif:
                generated_notifications.append(notif)

        if payload.fuel_level < 10.0 and climate and climate.webasto_active:
            climate.webasto_active = False
            climate.is_active = False
            notif = cls._create_notification_if_not_recent(
                db,
                vehicle_id,
                "WEBASTO",
                "Ogrzewanie postojowe Webasto zostało automatycznie wyłączone z powodu niskiego stanu paliwa (<10%).",
            )
            if notif:
                generated_notifications.append(notif)

        if payload.tire_pressure_psi < 28.0:
            notif = cls._create_notification_if_not_recent(
                db,
                vehicle_id,
                "TIRE_PRESSURE",
                f"Wykryto niskie ciśnienie w ogumieniu ({payload.tire_pressure_psi:.1f} PSI). Zalecane: 32.0 PSI.",
            )
            if notif:
                generated_notifications.append(notif)

        if payload.battery_voltage < 11.8:
            notif = cls._create_notification_if_not_recent(
                db,
                vehicle_id,
                "BATTERY_LOW",
                f"Niskie napięcie akumulatora ({payload.battery_voltage:.2f} V). Ryzyko problemów z rozruchem.",
            )
            if notif:
                generated_notifications.append(notif)

        db.commit()
        db.refresh(telemetry)

        TELEMETRY_PACKETS_TOTAL.labels(vehicle_id=str(vehicle_id)).inc()
        VEHICLE_SPEED_GAUGE.labels(vehicle_id=str(vehicle_id)).set(payload.speed)
        VEHICLE_FUEL_GAUGE.labels(vehicle_id=str(vehicle_id)).set(payload.fuel_level)
        VEHICLE_INTERIOR_TEMP_GAUGE.labels(vehicle_id=str(vehicle_id)).set(payload.current_interior_temp)

        return telemetry, generated_notifications

    @classmethod
    def update_climate_settings(
        cls,
        db: Session,
        vehicle_id: int,
        payload: ClimateUpdateRequest,
    ) -> ClimateSettings:
        vehicle = cls.get_vehicle_or_404(db, vehicle_id)
        latest_telemetry = (
            db.query(VehicleTelemetry)
            .filter(VehicleTelemetry.vehicle_id == vehicle_id)
            .order_by(desc(VehicleTelemetry.updated_at))
            .first()
        )

        if payload.webasto_active and latest_telemetry:
            if float(latest_telemetry.fuel_level) < 10.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nie można uruchomić systemu Webasto: poziom paliwa poniżej 10%.",
                )
            if float(latest_telemetry.battery_voltage) < 11.5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nie można uruchomić systemu Webasto: napięcie akumulatora poniżej 11.5V.",
                )

        climate = vehicle.climate_setting
        if not climate:
            climate = ClimateSettings(vehicle_id=vehicle_id)
            db.add(climate)

        climate.target_temperature = payload.target_temperature
        climate.is_active = payload.is_active
        climate.webasto_active = payload.webasto_active
        climate.fan_speed = payload.fan_speed
        climate.scheduled_time = payload.scheduled_time
        climate.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(climate)
        return climate

    @classmethod
    def set_central_lock(cls, db: Session, vehicle_id: int, is_locked: bool) -> Vehicle:
        vehicle = cls.get_vehicle_or_404(db, vehicle_id)
        vehicle.is_locked = is_locked

        state_label = "Zablokowano (zamknięto)" if is_locked else "Odblokowano (otwarto)"
        db.add(
            Notification(
                vehicle_id=vehicle_id,
                type="SECURITY",
                message=f"{state_label} centralny zamek zdalnie z aplikacji.",
                is_read=False,
            )
        )
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @classmethod
    def register_obd_error(
        cls,
        db: Session,
        vehicle_id: int,
        payload: ObdErrorCreateRequest,
    ) -> ObdError:
        cls.get_vehicle_or_404(db, vehicle_id)

        existing = (
            db.query(ObdError)
            .filter(
                ObdError.vehicle_id == vehicle_id,
                ObdError.code == payload.code,
                ObdError.is_active.is_(True),
            )
            .first()
        )
        if existing:
            return existing

        obd_err = ObdError(
            vehicle_id=vehicle_id,
            code=payload.code,
            description=payload.description,
            severity=payload.severity,
            is_active=True,
        )
        db.add(obd_err)

        db.add(
            Notification(
                vehicle_id=vehicle_id,
                type="OBD_ERROR",
                message=f"Błąd OBD-II [{payload.code}]: {payload.description}",
                is_read=False,
            )
        )
        db.commit()
        db.refresh(obd_err)

        active_count = (
            db.query(ObdError)
            .filter(ObdError.vehicle_id == vehicle_id, ObdError.is_active.is_(True))
            .count()
        )
        VEHICLE_OBD_ERRORS_GAUGE.labels(vehicle_id=str(vehicle_id)).set(active_count)
        return obd_err

    @classmethod
    def clear_obd_errors(cls, db: Session, vehicle_id: int) -> int:
        cls.get_vehicle_or_404(db, vehicle_id)
        latest_telemetry = (
            db.query(VehicleTelemetry)
            .filter(VehicleTelemetry.vehicle_id == vehicle_id)
            .order_by(desc(VehicleTelemetry.updated_at))
            .first()
        )
        if latest_telemetry and latest_telemetry.speed > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kasowanie błędów OBD-II jest dozwolone wyłącznie na postoju (prędkość 0 km/h).",
            )

        active_errors = (
            db.query(ObdError)
            .filter(ObdError.vehicle_id == vehicle_id, ObdError.is_active.is_(True))
            .all()
        )
        cleared_count = len(active_errors)
        for err in active_errors:
            err.is_active = False

        if cleared_count > 0:
            db.add(
                Notification(
                    vehicle_id=vehicle_id,
                    type="OBD_CLEAR",
                    message=f"Wykasowano {cleared_count} kod(ów) błędów z pamięci sterownika OBD-II.",
                    is_read=False,
                )
            )
        db.commit()
        VEHICLE_OBD_ERRORS_GAUGE.labels(vehicle_id=str(vehicle_id)).set(0)
        return cleared_count

    @classmethod
    def mark_notification_read(
        cls,
        db: Session,
        vehicle_id: int,
        notification_id: int,
    ) -> Notification:
        cls.get_vehicle_or_404(db, vehicle_id)
        notif = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.vehicle_id == vehicle_id)
            .first()
        )
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Powiadomienie o ID={notification_id} dla pojazdu ID={vehicle_id} nie istnieje.",
            )
        notif.is_read = True
        db.commit()
        db.refresh(notif)
        return notif

    @classmethod
    def delete_notification(cls, db: Session, vehicle_id: int, notification_id: int) -> None:
        cls.get_vehicle_or_404(db, vehicle_id)
        notif = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.vehicle_id == vehicle_id)
            .first()
        )
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Powiadomienie o ID={notification_id} dla pojazdu ID={vehicle_id} nie istnieje.",
            )
        db.delete(notif)
        db.commit()

    @classmethod
    def start_trip(cls, db: Session, vehicle_id: int, payload: TripStartRequest) -> Trip:
        cls.get_vehicle_or_404(db, vehicle_id)
        trip = Trip(
            vehicle_id=vehicle_id,
            start_location=payload.start_location,
            distance_km=0.0,
            avg_consumption=6.4,
            ecodriving_score=100,
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return trip

    @classmethod
    def end_trip(cls, db: Session, vehicle_id: int, trip_id: int, payload: TripEndRequest) -> Trip:
        cls.get_vehicle_or_404(db, vehicle_id)
        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id, Trip.vehicle_id == vehicle_id)
            .first()
        )
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trasa o ID={trip_id} dla pojazdu ID={vehicle_id} nie została znaleziona.",
            )
        if trip.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Trasa o ID={trip_id} została już wcześniej zakończona.",
            )

        samples = (
            db.query(VehicleTelemetry)
            .filter(
                VehicleTelemetry.vehicle_id == vehicle_id,
                VehicleTelemetry.updated_at >= trip.started_at,
            )
            .all()
        )

        score = 100
        avg_consumption = 6.2

        if samples:
            high_rpm_ratio = sum(1 for s in samples if s.engine_rpm > 3500) / len(samples)
            speeding_ratio = sum(1 for s in samples if s.speed > 110) / len(samples)
            low_tire_penalty = 8 if any(float(s.tire_pressure_psi) < 29.0 for s in samples) else 0

            score_deduction = int((high_rpm_ratio * 35) + (speeding_ratio * 40) + low_tire_penalty)
            score = max(10, min(100, 100 - score_deduction))
            avg_consumption = round(5.8 + (high_rpm_ratio * 2.1) + (speeding_ratio * 1.8), 2)

        trip.end_location = payload.end_location
        trip.distance_km = payload.distance_km
        trip.avg_consumption = avg_consumption
        trip.ecodriving_score = score
        trip.ended_at = datetime.now(timezone.utc)

        db.add(
            Notification(
                vehicle_id=vehicle_id,
                type="TRIP_SUMMARY",
                message=(
                    f"Zakończono trasę ({payload.distance_km:.1f} km). "
                    f"Średnie spalanie: {avg_consumption} L/100km, Ecodriving: {score}/100 pkt."
                ),
                is_read=False,
            )
        )
        db.commit()
        db.refresh(trip)
        return trip

    @classmethod
    def delete_trip(cls, db: Session, vehicle_id: int, trip_id: int) -> None:
        cls.get_vehicle_or_404(db, vehicle_id)
        trip = (
            db.query(Trip)
            .filter(Trip.id == trip_id, Trip.vehicle_id == vehicle_id)
            .first()
        )
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trasa o ID={trip_id} dla pojazdu ID={vehicle_id} nie istnieje.",
            )
        db.delete(trip)
        db.commit()
