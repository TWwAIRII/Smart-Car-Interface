import os
import time
import math
import random
import requests

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api")
VEHICLE_ID = int(os.getenv("VEHICLE_ID", "1"))
INTERVAL_SEC = float(os.getenv("SIMULATION_INTERVAL_SEC", "2.0"))
SIMULATOR_USERNAME = os.getenv("SIMULATOR_USERNAME", "kierowca")
SIMULATOR_PASSWORD = os.getenv("SIMULATOR_PASSWORD", "corsa123")

# Katalog realistycznych kodów błędów OBD-II dla Opla Corsy B (silniki X14XE / X12SZ)
CORSA_OBD_CATALOG = [
    ("P0170", "Czujnik O2 (Bank 1) - usterka dostrajania składu mieszanki", "warning"),
    ("P0400", "Układ recyrkulacji spalin (EGR) - nieprawidłowy przepływ", "warning"),
    ("P0115", "Czujnik temperatury płynu chłodzącego (ECT) - sygnał poza zakresem", "warning"),
    ("P0335", "Czujnik położenia wału korbowego (CKP) - brak sygnału", "critical"),
    ("P0505", "Układ regulacji biegu jałowego (silniczek krokowy) - usterka", "warning"),
]


class GreenCorsaSimulator:
    def __init__(self):
        self.speed = 0
        self.engine_rpm = 0
        self.fuel_level = 68.5
        self.tire_pressure_psi = 32.0
        self.interior_temp = 14.0
        self.exterior_temp = 10.5
        self.battery_voltage = 12.6
        self.is_driving = True

        # Współrzędne początkowe (Kraków)
        self.lat = 50.064650
        self.lon = 19.944980
        self.step_counter = 0

        # Stan odczytywany z backendu (sterowanie przez użytkownika w aplikacji)
        self.webasto_active = False
        self.climate_active = False
        self.target_temp = 21.0
        self.fan_speed = 1
        self.is_locked = True

        # Sesja i token JWT
        self.access_token = None

    def _auth_headers(self) -> dict:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def authenticate(self) -> bool:
        """Loguje symulator do chronionego API i pobiera token JWT."""
        try:
            resp = requests.post(
                f"{BACKEND_API_URL}/auth/login",
                json={"username": SIMULATOR_USERNAME, "password": SIMULATOR_PASSWORD},
                timeout=3,
            )
            if resp.status_code == 200:
                self.access_token = resp.json().get("access_token")
                print(f"[Simulator] Zalogowano pomyślnie jako '{SIMULATOR_USERNAME}' (JWT aktywny).")
                return True
            print(
                f"[Simulator] Błąd logowania ({resp.status_code}): {resp.text}"
            )
        except Exception as exc:
            print(f"[Simulator] Oczekiwanie na backend podczas logowania: {exc}")
        return False

    def ensure_authenticated(self) -> bool:
        if self.access_token:
            return True
        return self.authenticate()

    def sync_state_from_server(self):
        """Pobiera aktualne nastawy Webasto, nawiewu i zamka z serwera."""
        if not self.ensure_authenticated():
            return
        try:
            resp = requests.get(
                f"{BACKEND_API_URL}/vehicles/{VEHICLE_ID}/dashboard",
                headers=self._auth_headers(),
                timeout=3,
            )
            if resp.status_code == 401:
                self.access_token = None
                if self.authenticate():
                    resp = requests.get(
                        f"{BACKEND_API_URL}/vehicles/{VEHICLE_ID}/dashboard",
                        headers=self._auth_headers(),
                        timeout=3,
                    )
            if resp.status_code == 200:
                data = resp.json()
                self.is_locked = data.get("is_locked", True)
                climate = data.get("climate")
                if climate:
                    self.webasto_active = climate.get("webasto_active", False)
                    self.climate_active = climate.get("is_active", False)
                    self.target_temp = float(climate.get("target_temperature", 21.0))
                    self.fan_speed = int(climate.get("fan_speed", 0))
        except Exception as exc:
            print(f"[Simulator] Oczekiwanie na połączenie z backendem: {exc}")

    def step_physics(self):
        self.step_counter += 1

        phase = self.step_counter % 60
        if phase < 40 and not self.is_locked:
            self.is_driving = True
            target_speed = 45 + int(25 * math.sin(self.step_counter * 0.15))
            self.speed = max(0, min(115, target_speed + random.randint(-3, 3)))
            self.engine_rpm = 1800 + int(self.speed * 26) + random.randint(-80, 80)
            self.battery_voltage = round(14.15 + random.uniform(-0.1, 0.1), 2)
            self.fuel_level = max(5.0, self.fuel_level - 0.03)
            self.lat += 0.00018 * math.cos(self.step_counter * 0.05)
            self.lon += 0.00024 * math.sin(self.step_counter * 0.05)
        else:
            self.is_driving = False
            self.speed = 0
            self.engine_rpm = 0
            self.battery_voltage = round(
                12.55 - (0.15 if self.webasto_active else 0.0) + random.uniform(-0.04, 0.04), 2
            )

        fan_multiplier = 1.0 + (self.fan_speed * 0.25)
        if self.webasto_active:
            diff = self.target_temp - self.interior_temp
            self.interior_temp += (0.22 * fan_multiplier) if diff > 0 else -0.05
            self.fuel_level = max(5.0, self.fuel_level - 0.01)
        elif self.climate_active and self.fan_speed > 0:
            diff = self.exterior_temp - self.interior_temp
            self.interior_temp += diff * 0.08 * fan_multiplier
        else:
            diff = self.exterior_temp - self.interior_temp
            self.interior_temp += diff * 0.03

        self.interior_temp = round(self.interior_temp, 1)
        self.fuel_level = round(self.fuel_level, 2)
        self.tire_pressure_psi = round(31.8 + random.uniform(-0.2, 0.2), 1)

    def send_telemetry(self):
        if not self.ensure_authenticated():
            return
        payload = {
            "speed": self.speed,
            "fuel_level": self.fuel_level,
            "tire_pressure_psi": self.tire_pressure_psi,
            "current_interior_temp": self.interior_temp,
            "current_exterior_temp": self.exterior_temp,
            "battery_voltage": self.battery_voltage,
            "engine_rpm": self.engine_rpm,
            "latitude": round(self.lat, 6),
            "longitude": round(self.lon, 6),
        }
        try:
            resp = requests.post(
                f"{BACKEND_API_URL}/vehicles/{VEHICLE_ID}/telemetry",
                json=payload,
                headers=self._auth_headers(),
                timeout=3,
            )
            if resp.status_code == 401:
                self.access_token = None
                if self.authenticate():
                    resp = requests.post(
                        f"{BACKEND_API_URL}/vehicles/{VEHICLE_ID}/telemetry",
                        json=payload,
                        headers=self._auth_headers(),
                        timeout=3,
                    )
            if resp.status_code in (200, 201):
                data = resp.json()
                print(
                    f"[Corsa B Sim] V={self.speed} km/h | RPM={self.engine_rpm} | "
                    f"Paliwo={self.fuel_level}% (Zasięg: {data.get('estimated_range_km')} km) | "
                    f"Temp wew={self.interior_temp}°C (Webasto={'ON' if self.webasto_active else 'OFF'}, Nawiew={self.fan_speed})"
                )
        except Exception as exc:
            print(f"[Corsa B Sim] Błąd wysyłania telemetrii: {exc}")

    def maybe_trigger_obd_fault(self):
        if not self.access_token:
            return
        if self.step_counter % 45 == 0 and random.random() < 0.35:
            code, desc, severity = random.choice(CORSA_OBD_CATALOG)
            try:
                requests.post(
                    f"{BACKEND_API_URL}/vehicles/{VEHICLE_ID}/obd",
                    json={"code": code, "description": desc, "severity": severity},
                    headers=self._auth_headers(),
                    timeout=3,
                )
                print(f"[Corsa B Sim] Wygenerowano kod błędu OBD-II: {code} ({desc})")
            except Exception:
                pass


if __name__ == "__main__":
    print("=== Uruchomiono symulator pojazdu SmartCarInterface (Opel Corsa B Green) ===")
    sim = GreenCorsaSimulator()
    while True:
        sim.sync_state_from_server()
        sim.step_physics()
        sim.send_telemetry()
        sim.maybe_trigger_obd_fault()
        time.sleep(INTERVAL_SEC)
