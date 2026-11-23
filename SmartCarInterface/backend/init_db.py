"""
Skrypt CLI do inicjalizacji schematu bazy danych PostgreSQL oraz zasilenia
jej danymi startowymi (seed) dla systemu SmartCarInterface.

Przykłady użycia (w kontenerze Docker):
    docker compose exec backend python init_db.py
    docker compose exec backend python init_db.py --check
    docker compose exec backend python init_db.py --reset
    docker compose exec backend python init_db.py --no-seed
"""

import argparse
import sys
import time
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

# Zapewnia poprawne importy niezaleznie od katalogu roboczego
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.entities import (
    ClimateSettings,
    Notification,
    ObdError,
    Trip,
    User,
    Vehicle,
    VehicleLocation,
    VehicleTelemetry,
)

ALL_MODELS = [
    User,
    Vehicle,
    VehicleTelemetry,
    ClimateSettings,
    Notification,
    VehicleLocation,
    Trip,
    ObdError,
]


def wait_for_database(max_retries: int = 10, delay_sec: float = 2.0) -> None:
    """Weryfikuje polaczenie z baza PostgreSQL przed uruchomieniem inicjalizacji."""
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[OK] Polaczenie z baza danych PostgreSQL zostalo nawiazane.")
            return
        except OperationalError as exc:
            print(
                f"[WAIT] Proba {attempt}/{max_retries}: oczekiwanie na baze danych ({exc.orig})..."
            )
            time.sleep(delay_sec)
    raise RuntimeError("Nie udalo sie polaczyc z baza danych PostgreSQL.")


def create_schema(reset: bool = False) -> None:
    """Tworzy tabele na podstawie modeli ORM SQLAlchemy (opcjonalnie resetujac schemat)."""
    if reset:
        print("[WARN] Usuwanie istniejacych tabel (--reset)...")
        Base.metadata.drop_all(bind=engine)

    print("[INFO] Tworzenie schematu bazy danych (create_all)...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Schemat bazy danych jest gotowy.")


def seed_initial_data() -> None:
    """Dodaje domyslne konta (admin, kierowca) oraz domyslny pojazd, jesli baza jest pusta."""
    db = SessionLocal()
    try:
        added_users = 0
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    email="admin@smartcar.local",
                    password_hash=get_password_hash("admin123"),
                    role="admin",
                    is_active=True,
                )
            )
            added_users += 1

        if not db.query(User).filter(User.username == "kierowca").first():
            db.add(
                User(
                    username="kierowca",
                    email="kierowca@smartcar.local",
                    password_hash=get_password_hash("corsa123"),
                    role="driver",
                    is_active=True,
                )
            )
            added_users += 1

        if added_users:
            db.commit()
            print(f"[OK] Dodano domyslnych uzytkownikow: {added_users}.")
        else:
            print("[SKIP] Domyslni uzytkownicy juz istnieja w bazie.")

        if not db.query(Vehicle).first():
            vehicle = Vehicle(
                vin="W0L000073W4123456",
                make="Opel",
                model="Corsa B 1.4i 16V (Green Edition)",
                year=1998,
                is_locked=True,
                fuel_tank_capacity_l=46.00,
                base_avg_consumption=6.40,
            )
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

            db.add_all(
                [
                    ClimateSettings(
                        vehicle_id=vehicle.id,
                        target_temperature=21.5,
                        is_active=False,
                        webasto_active=False,
                        fan_speed=1,
                        scheduled_time="07:30",
                    ),
                    VehicleTelemetry(
                        vehicle_id=vehicle.id,
                        speed=0,
                        fuel_level=68.5,
                        tire_pressure_psi=32.0,
                        estimated_range_km=492,
                        current_interior_temp=14.5,
                        current_exterior_temp=11.0,
                        battery_voltage=12.65,
                        engine_rpm=0,
                    ),
                    VehicleLocation(
                        vehicle_id=vehicle.id,
                        latitude=50.064650,
                        longitude=19.944980,
                    ),
                ]
            )
            db.commit()
            print(f"[OK] Dodano domyslny pojazd (ID={vehicle.id}, VIN={vehicle.vin}).")
        else:
            print("[SKIP] Pojazd startowy juz istnieje w bazie.")
    finally:
        db.close()


def print_database_summary() -> None:
    """Wyswietla liste tabel obecnych w bazie PostgreSQL oraz liczbe rekordow."""
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    print("\n--- Stan tabel w bazie danych ---")
    if not table_names:
        print("(Brak tabel w bazie danych)")
        return

    with engine.connect() as conn:
        for table in table_names:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            print(f" - {table:<22} | rekordow: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicjalizacja schematu i danych startowych PostgreSQL dla SmartCarInterface."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Usuwa wszystkie istniejace tabele i tworzy schemat od nowa.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Tworzy wylacznie schemat tabel bez zasilania danymi startowymi.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Tylko weryfikuje polaczenie oraz wyswietla tabele i liczbe rekordow.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wait_for_database()

    if args.check:
        print_database_summary()
        return

    create_schema(reset=args.reset)
    if not args.no_seed:
        seed_initial_data()

    print_database_summary()


if __name__ == "__main__":
    main()
