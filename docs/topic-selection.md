### 1. Opis tematu

System IoT typu _Connected Car_ stylizowany na interfejsy nowoczesnych aut elektrycznych (w stylu Tesli), dedykowany do klasycznego pojazdu miejskiego. Aplikacja łączy retro-motoryzację z nowoczesnym, wieloplatformowym panelem kontrolnym.

### 2. Cel projektu

Stworzenie rozproszonego systemu do zdalnego monitorowania telemetrii pojazdu w czasie rzeczywistym (OBD-II, sensory), kontroli modułów komfortu (Webasto, zamek centralny) oraz monitoringu kamer.

### 3. Zakres funkcjonalny

- **Dashboard (Live):** Strumieniowanie parametrów przez WebSockets (paliwo i szacowany zasięg, temp. wnętrza/zewnętrzna, napięcie akumulatora, kody błędów OBD-II/DTC, podgląd z kamery pokładowej).
    
- **Zarządzanie:** Zdalne ryglowanie/odryglowywanie zamka centralnego, sterowanie i harmonogram pracy ogrzewania Webasto oraz wentylacji, kasowanie błędów OBD-II + panel symulatora danych wejściowych.
    
- **Panel Administratora:** Zarządzanie kontami użytkowników (rejestracja, aktywacja/blokowanie) oraz uprawnieniami (role: Właściciel, Gość).
    
- **Monitoring:** Zbieranie metryk serwerowych i aplikacyjnych (aktywne sesje WS, czas odpowiedzi API, obciążenie kontenerów).
    

### 4. Proponowane technologie

- **Frontend:** React Native
    
- **Backend:** Node.js (Fastify/Express) lub Python (FastAPI) – REST API + WebSockets
    
- **Baza danych:** PostgreSQL / SQLite
    
- **IoT / Telemetria:** Skrypt symulacyjny / integracja OBD-II (Python)
    
- **DevOps & Monitoring:** Docker, Docker Compose, Prometheus, Grafana