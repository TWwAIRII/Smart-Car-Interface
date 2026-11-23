import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.core.metrics import API_REQUEST_LATENCY
from app.core.exceptions import register_exception_handlers
from app.models.entities import (
    User,
    Vehicle,
    ClimateSettings,
    VehicleTelemetry,
    VehicleLocation,
)
from app.routers import auth_admin, vehicles


def seed_initial_data():
    """Tworzy domyślne konta (admin / kierowca) oraz domyślny pojazd (Zielona Corsa B) jeśli baza jest pusta."""
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin_user = User(
                username="admin",
                email="admin@smartcar.local",
                password_hash=get_password_hash("admin123"),
                role="admin",
                is_active=True,
            )
            driver_user = User(
                username="kierowca",
                email="kierowca@smartcar.local",
                password_hash=get_password_hash("corsa123"),
                role="driver",
                is_active=True,
            )
            db.add_all([admin_user, driver_user])
            db.commit()

        if not db.query(Vehicle).first():
            corsa = Vehicle(
                vin="W0L000073W4123456",
                make="Opel",
                model="Corsa B 1.4i 16V (Green Edition)",
                year=1998,
                is_locked=True,
                fuel_tank_capacity_l=46.00,
                base_avg_consumption=6.40,
            )
            db.add(corsa)
            db.commit()
            db.refresh(corsa)

            climate = ClimateSettings(
                vehicle_id=corsa.id,
                target_temperature=21.5,
                is_active=False,
                webasto_active=False,
                fan_speed=1,
                scheduled_time="07:30",
            )
            telemetry = VehicleTelemetry(
                vehicle_id=corsa.id,
                speed=0,
                fuel_level=68.5,
                tire_pressure_psi=32.0,
                estimated_range_km=492,
                current_interior_temp=14.5,
                current_exterior_temp=11.0,
                battery_voltage=12.65,
                engine_rpm=0,
            )
            location = VehicleLocation(
                vehicle_id=corsa.id,
                latitude=50.064650,
                longitude=19.944980,
            )
            db.add_all([climate, telemetry, location])
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    yield


app = FastAPI(
    title="SmartCarInterface API",
    description="Backend systemu Connected Car (REST API CRUD, Telemetria, OBD-II, Webasto, Zamek Centralny, Panel Admina, Prometheus).",
    version="1.1.0",
    lifespan=lifespan,
)

# Rejestracja globalnej obsługi błędów i wyjątków
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Udostępnienie nagrań MP4 symulujących kamery pokładowe
media_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "media"))
os.makedirs(media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")


@app.middleware("http")
async def prometheus_latency_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start_time
    if request.url.path != "/metrics":
        API_REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=str(response.status_code),
        ).observe(elapsed)
    return response


@app.get("/metrics", tags=["Monitoring (Prometheus)"])
def prometheus_metrics():
    """Endpoint wystawiany dla serwera Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health", tags=["Status"])
def healthcheck():
    return {"status": "ok", "service": "SmartCarInterface Backend"}


app.include_router(auth_admin.router)
app.include_router(vehicles.router)
