# Dokumentacja REST API — SmartCarInterface

Dokumentacja zawiera opis dostępnych endpointów, zasady uwierzytelniania (JWT + RBAC), przykładowe zapytania `curl` oraz scenariusze testowe wykorzystane do weryfikacji działania backendu systemu **SmartCarInterface** (Opel Corsa B IoT).

* **Bazowy adres API:** `http://localhost:8000`
* **Interaktywna dokumentacja (Swagger UI):** `http://localhost:8000/docs`
* **Dokumentacja ReDoc:** `http://localhost:8000/redoc`
* **Metryki Prometheus:** `http://localhost:8000/metrics`
* **Strumienie kamer pokładowych:**
  * Przód: `http://localhost:8000/media/front_camera.mp4`
  * Tył: `http://localhost:8000/media/rear_camera.mp4`

---

## 1. Uwierzytelnianie i role (JWT + RBAC)

Wszystkie chronione endpointy wymagają przesłania ważnego tokenu JWT w nagłówku HTTP:

```http
Authorization: Bearer <TWÓJ_TOKEN_JWT>
```

### Domyślne konta startowe (seed)

| Login (`username`) | Hasło (`password`) | Rola (`role`) | Zakres uprawnień |
| :--- | :--- | :--- | :--- |
| `admin` | `admin123` | `admin` | Pełny dostęp (Panel Admina, CRUD floty, sterowanie pojazdem, odczyt) |
| `kierowca` | `corsa123` | `driver` | Odczyt danych oraz sterowanie pojazdem (zamek, Webasto, OBD-II, trasy) |
| *(nowe konto)* | *(dowolne)* | `guest` / `driver` | Rola `guest` posiada wyłącznie dostęp do odczytu (`GET` i WebSocket) |

### Macierz dostępu do zasobów

| Poziom dostępu | Dozwolone role | Endpointy |
| :--- | :--- | :--- |
| **Publiczne** | Wszyscy | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/token`, `GET /api/health`, `GET /metrics` |
| **Odczyt (JWT)** | `guest`, `driver`, `admin` | `GET /api/auth/me`, `GET /api/vehicles`, `GET /api/vehicles/{id}`, `/dashboard`, `/obd`, `/notifications`, `/locations`, `/trips`, `WS /api/vehicles/ws/{id}` |
| **Sterowanie (JWT)** | `driver`, `admin` | `POST /telemetry`, `PUT /climate`, `POST /lock`, `POST/DELETE /obd`, `PATCH/DELETE /notifications/{id}`, `POST /trips/start`, `POST /trips/{id}/end`, `DELETE /trips/{id}` |
| **Administracja (JWT)** | `admin` | `POST/PUT/DELETE /api/vehicles`, `GET/PATCH/DELETE /api/admin/users` |

---

## 2. Moduł Autoryzacji (`/api/auth`)

### 2.1. Rejestracja nowego użytkownika
* **Endpoint:** `POST /api/auth/register`
* **Kody HTTP:** `201 Created`, `409 Conflict` (zajęty login lub e-mail), `422 Unprocessable Entity`

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "janek_corsa",
    "email": "janek@smartcar.local",
    "password": "haslo123"
  }'
```

**Przykładowa odpowiedź (`201 Created`):**
```json
{
  "id": 3,
  "username": "janek_corsa",
  "email": "janek@smartcar.local",
  "role": "driver",
  "is_active": true,
  "created_at": "2026-04-15T12:00:00Z"
}
```

### 2.2. Logowanie (JSON — dla aplikacji klienckiej i symulatora)
* **Endpoint:** `POST /api/auth/login`
* **Kody HTTP:** `200 OK`, `401 Unauthorized`, `403 Forbidden` (konto zablokowane)

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

**Przykładowa odpowiedź (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

> **Wskazówka (Bash):** Aby szybko zapisać token w zmiennej środowiskowej do poniższych zapytań:
> ```bash
> TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
>   -H "Content-Type: application/json" \
>   -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
> ```

### 2.3. Logowanie formularzem OAuth2 (dla przycisku Authorize w Swagger UI)
* **Endpoint:** `POST /api/auth/token`
* **Kody HTTP:** `200 OK`, `401 Unauthorized`

```bash
curl -X POST "http://localhost:8000/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=kierowca&password=corsa123"
```

### 2.4. Pobranie profilu zalogowanego użytkownika
* **Endpoint:** `GET /api/auth/me`
* **Wymagane uprawnienia:** JWT (`guest` / `driver` / `admin`)

```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 3. Zarządzanie pojazdami — CRUD (`/api/vehicles`)

### 3.1. Lista wszystkich pojazdów
* **Endpoint:** `GET /api/vehicles`
* **Kody HTTP:** `200 OK`, `401 Unauthorized`

```bash
curl -X GET "http://localhost:8000/api/vehicles" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.2. Dodanie nowego pojazdu
* **Endpoint:** `POST /api/vehicles`
* **Wymagane uprawnienia:** `admin`
* **Kody HTTP:** `201 Created`, `403 Forbidden`, `409 Conflict` (duplikat VIN), `422 Unprocessable Entity`

```bash
curl -X POST "http://localhost:8000/api/vehicles" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Opel Corsa B GSi",
    "make": "Opel",
    "model": "Corsa B",
    "year": 1998,
    "vin": "W0L000073W4999999",
    "fuel_tank_capacity_l": 46.0,
    "base_fuel_consumption": 7.2
  }'
```

### 3.3. Szczegóły pojazdu
* **Endpoint:** `GET /api/vehicles/{vehicle_id}`
* **Kody HTTP:** `200 OK`, `404 Not Found`

```bash
curl -X GET "http://localhost:8000/api/vehicles/1" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.4. Aktualizacja danych pojazdu
* **Endpoint:** `PUT /api/vehicles/{vehicle_id}`
* **Wymagane uprawnienia:** `admin`
* **Kody HTTP:** `200 OK`, `404 Not Found`, `409 Conflict`

```bash
curl -X PUT "http://localhost:8000/api/vehicles/2" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Opel Corsa B Sport",
    "make": "Opel",
    "model": "Corsa B",
    "year": 1999,
    "vin": "W0L000073W4999999",
    "fuel_tank_capacity_l": 46.0,
    "base_fuel_consumption": 6.8
  }'
```

### 3.5. Usunięcie pojazdu
* **Endpoint:** `DELETE /api/vehicles/{vehicle_id}`
* **Wymagane uprawnienia:** `admin`
* **Kody HTTP:** `204 No Content`, `404 Not Found`

```bash
curl -X DELETE "http://localhost:8000/api/vehicles/2" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4. Dashboard, Telemetria i Sterowanie zdalne

### 4.1. Zbiorczy stan pojazdu (Dashboard)
Zwraca najnowszy odczyt telemetrii, dynamicznie obliczony zasięg (`estimated_range_km`), ustawienia klimatyzacji/Webasto, stan zamka, ostatnią pozycję GPS, aktywne błędy OBD-II, nieprzeczytane powiadomienia oraz adresy kamer.
* **Endpoint:** `GET /api/vehicles/{vehicle_id}/dashboard`
* **Kody HTTP:** `200 OK`, `404 Not Found`

```bash
curl -X GET "http://localhost:8000/api/vehicles/1/dashboard" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.2. Wysłanie paczki telemetrii (Ingest z symulatora)
* **Endpoint:** `POST /api/vehicles/{vehicle_id}/telemetry`
* **Wymagane uprawnienia:** `driver` / `admin`
* **Kody HTTP:** `201 Created`, `404 Not Found`, `422 Unprocessable Entity`

```bash
curl -X POST "http://localhost:8000/api/vehicles/1/telemetry" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "speed": 52.5,
    "rpm": 2650,
    "fuel_level": 68.4,
    "battery_voltage": 13.8,
    "engine_temp": 89.0,
    "interior_temp": 20.5,
    "exterior_temp": 8.2,
    "latitude": 50.0647,
    "longitude": 19.9450
  }'
```

### 4.3. Sterowanie zamkiem centralnym
Odblokowanie zamka (`"is_locked": false`) pozwala symulatorowi rozpocząć jazdę.
* **Endpoint:** `POST /api/vehicles/{vehicle_id}/lock`
* **Wymagane uprawnienia:** `driver` / `admin`
* **Kody HTTP:** `200 OK`, `403 Forbidden`, `404 Not Found`

```bash
curl -X POST "http://localhost:8000/api/vehicles/1/lock" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_locked": false}'
```

### 4.4. Sterowanie klimatyzacją i ogrzewaniem postojowym Webasto
> **Reguły biznesowe:** System blokuje uruchomienie Webasto kodem `400 Bad Request`, gdy napięcie akumulatora spadnie poniżej `11.5 V` lub poziom paliwa spadnie poniżej `10%`.

* **Endpoint:** `PUT /api/vehicles/{vehicle_id}/climate`
* **Wymagane uprawnienia:** `driver` / `admin`
* **Kody HTTP:** `200 OK`, `400 Bad Request`, `404 Not Found`, `422 Unprocessable Entity`

```bash
curl -X PUT "http://localhost:8000/api/vehicles/1/climate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_temperature": 22.5,
    "is_active": true,
    "webasto_active": true,
    "fan_speed": 3,
    "scheduled_time": "07:30"
  }'
```

---

## 5. Diagnostyka OBD-II, Powiadomienia i Trasy

### 5.1. Odczyt, dodawanie i kasowanie błędów OBD-II
> **Reguła bezpieczeństwa:** Kasowanie błędów OBD-II (`DELETE`) podczas jazdy (`speed > 0`) jest blokowane kodem `400 Bad Request`.

* **Lista aktywnych błędów (`GET`):**
```bash
curl -X GET "http://localhost:8000/api/vehicles/1/obd" \
  -H "Authorization: Bearer $TOKEN"
```

* **Rejestracja kodu błędu (`POST` -> `201 Created`):**
```bash
curl -X POST "http://localhost:8000/api/vehicles/1/obd" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "P0170",
    "description": "Nieprawidłowy skład mieszanki (czujnik O2)",
    "severity": "warning"
  }'
```

* **Kasowanie aktywnych błędów na postoju (`DELETE` -> `200 OK` lub `400 Bad Request` w ruchu):**
```bash
curl -X DELETE "http://localhost:8000/api/vehicles/1/obd" \
  -H "Authorization: Bearer $TOKEN"
```

### 5.2. Powiadomienia i historia lokalizacji GPS
* **Lista powiadomień (`GET`):**
```bash
curl -X GET "http://localhost:8000/api/vehicles/1/notifications" \
  -H "Authorization: Bearer $TOKEN"
```

* **Oznaczenie powiadomienia jako przeczytane (`PATCH` -> `200 OK` / `404 Not Found`):**
```bash
curl -X PATCH "http://localhost:8000/api/vehicles/1/notifications/1/read" \
  -H "Authorization: Bearer $TOKEN"
```

* **Usunięcie powiadomienia (`DELETE` -> `204 No Content` / `404 Not Found`):**
```bash
curl -X DELETE "http://localhost:8000/api/vehicles/1/notifications/1" \
  -H "Authorization: Bearer $TOKEN"
```

* **Historia lokalizacji GPS (`GET`):**
```bash
curl -X GET "http://localhost:8000/api/vehicles/1/locations" \
  -H "Authorization: Bearer $TOKEN"
```

### 5.3. Rejestr tras i punktacja Ecodrivingu
* **Rozpoczęcie trasy (`POST` -> `201 Created`):**
```bash
curl -X POST "http://localhost:8000/api/vehicles/1/trips/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_location": "Kraków, Politechnika"}'
```

* **Zakończenie trasy i wyliczenie `ecodriving_score` (`POST` -> `200 OK` / `409 Conflict` jeśli już zakończona):**
```bash
curl -X POST "http://localhost:8000/api/vehicles/1/trips/1/end" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "end_location": "Wieliczka, Rynek",
    "distance_km": 14.5
  }'
```

* **Lista tras (`GET`) oraz usunięcie trasy (`DELETE` -> `204 No Content`):**
```bash
curl -X GET "http://localhost:8000/api/vehicles/1/trips" \
  -H "Authorization: Bearer $TOKEN"

curl -X DELETE "http://localhost:8000/api/vehicles/1/trips/1" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 6. Panel Administratora (`/api/admin/users`)

Wszystkie endpointy w tej sekcji wymagają tokenu JWT użytkownika o roli **`admin`** (dla roli `driver` i `guest` zwracają `403 Forbidden`).

* **Lista użytkowników (`GET`):**
```bash
curl -X GET "http://localhost:8000/api/admin/users" \
  -H "Authorization: Bearer $TOKEN"
```

* **Zmiana statusu aktywności lub roli użytkownika (`PATCH`):**
```bash
curl -X PATCH "http://localhost:8000/api/admin/users/2/status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false,
    "role": "guest"
  }'
```

* **Usunięcie użytkownika (`DELETE` -> `204 No Content`, blokada usunięcia własnego konta -> `400 Bad Request`):**
```bash
curl -X DELETE "http://localhost:8000/api/admin/users/3" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 7. Komunikacja w czasie rzeczywistym (WebSocket)

* **Endpoint:** `ws://localhost:8000/api/vehicles/ws/{vehicle_id}?token=<JWT>`
* **Autoryzacja:** Token JWT w parametrze query `?token=` lub nagłówku `Authorization: Bearer <JWT>`. Brak lub niepoprawny token skutkuje zamknięciem połączenia z kodem `1008 Policy Violation`.

**Przykładowy test z poziomu konsoli przeglądarki (JavaScript):**
```javascript
const ws = new WebSocket("ws://localhost:8000/api/vehicles/ws/1?token=TWOJ_TOKEN_JWT");
ws.onmessage = (event) => console.log("Telemetria na żywo:", JSON.parse(event.data));
```

---

## 8. Globalna obsługa błędów i przetestowane scenariusze

Wszystkie błędy API są przechwytywane przez globalne handlery w `backend/app/core/exceptions.py` i zwracane w jednolitym formacie JSON:

```json
{
  "status_code": 404,
  "error": "Not Found",
  "detail": "Pojazd o ID 999 nie został znaleziony.",
  "path": "/api/vehicles/999",
  "timestamp": "2026-04-15T12:15:30.123456+00:00"
}
```

### Zestawienie zweryfikowanych przypadków testowych (Swagger UI + `curl`)

| Scenariusz testowy | Zapytanie | Oczekiwany i uzyskany kod |
| :--- | :--- | :--- |
| Brak tokenu na chronionym zasobie | `GET /api/vehicles/1/dashboard` (bez nagłówka) | `401 Unauthorized` |
| Brak uprawnień roli `driver` do Panelu Admina | `GET /api/admin/users` (token `kierowca`) | `403 Forbidden` |
| Brak uprawnień roli `guest` do sterowania | `POST /api/vehicles/1/lock` (token `guest`) | `403 Forbidden` |
| Odczyt nieistniejącego zasobu | `GET /api/vehicles/999` | `404 Not Found` |
| Duplikat użytkownika przy rejestracji | `POST /api/auth/register` (istniejący login/mail) | `409 Conflict` |
| Duplikat numeru VIN przy dodawaniu auta | `POST /api/vehicles` (VIN `W0L000073W4123456`) | `409 Conflict` |
| Błąd walidacji danych wejściowych | `POST /api/vehicles` z `year: 1800` lub paliwo `150%` | `422 Unprocessable Entity` |
| Kasowanie błędów OBD-II podczas jazdy | `DELETE /api/vehicles/1/obd` przy `speed > 0` | `400 Bad Request` |
| Pełny cykl CRUD zasobu `vehicles` | `POST` -> `GET` -> `PUT` -> `DELETE` | `201` -> `200` -> `200` -> `204` |