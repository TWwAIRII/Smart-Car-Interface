from prometheus_client import Counter, Gauge, Histogram

TELEMETRY_PACKETS_TOTAL = Counter(
    "smartcar_telemetry_packets_total",
    "Całkowita liczba odebranych pakietów telemetrii z pojazdu",
    ["vehicle_id"]
)

ACTIVE_WEBSOCKET_CONNECTIONS = Gauge(
    "smartcar_active_websocket_connections",
    "Liczba aktywnych połączeń WebSocket (Dashboard + Pojazd)"
)

VEHICLE_SPEED_GAUGE = Gauge(
    "smartcar_vehicle_speed_kmh",
    "Aktualna prędkość pojazdu w km/h",
    ["vehicle_id"]
)

VEHICLE_FUEL_GAUGE = Gauge(
    "smartcar_fuel_level_percent",
    "Aktualny poziom paliwa w procentach",
    ["vehicle_id"]
)

VEHICLE_INTERIOR_TEMP_GAUGE = Gauge(
    "smartcar_interior_temp_celsius",
    "Temperatura wewnątrz kabiny w stopniach Celsjusza",
    ["vehicle_id"]
)

VEHICLE_OBD_ERRORS_GAUGE = Gauge(
    "smartcar_active_obd_errors_count",
    "Liczba aktywnych błędów OBD-II w pojeździe",
    ["vehicle_id"]
)

API_REQUEST_LATENCY = Histogram(
    "smartcar_http_request_duration_seconds",
    "Czas obsługi zapytań HTTP API",
    ["method", "endpoint", "status_code"]
)
