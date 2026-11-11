# SmartCarInterface — Connected Car System

System telemetrii, zdalnej diagnostyki OBD-II oraz kontroli peryferiów pojazdu typu Connected Car. Aplikacja udostępnia interfejs w stylu nowoczesnych systemów pokładowych smart car, umożliwiając bieżący podgląd parametrów silnika, poziomu paliwa, temperatur wewnątrz i na zewnątrz kabiny, sterowanie zamkiem centralnym oraz modułem dogrzewania postojowego i wentylacji.

---

## Użyte technologie

* **Frontend:** React Native, Expo, TypeScript, React Native for Web (wsparcie Web, Android, iOS)
* **Komunikacja w czasie rzeczywistym:** WebSockets
* **Backend API & Generator IoT:** Node.js / Express (lub Python FastAPI)
* **Baza danych:** PostgreSQL / SQLite
* **Konteneryzacja & Monitoring:** Docker, Prometheus, Grafana

---

## Instrukcja uruchomienia

### Wymagania wstępne
* Środowisko **Node.js** (wersja >= 18.x LTS) oraz menedżer pakietów **npm**
* *(Opcjonalnie dla urządzeń mobilnych)*: Aplikacja **Expo Go** (Android/iOS)

### Instalacja i uruchomienie

1. Sklonuj repozytorium:
   ```bash
   git clone https://github.com/TWwAIRII/Smart-Car-Interface.git
   cd SmartCarInterface
   ```

2. Zainstaluj zależności:
   ```bash
   npm install
   ```

3. Uruchom serwer developerski:
   ```bash
   npx expo start
   ```

### Dostępne platformy:
* **Przeglądarka internetowa (PC):** Wciśnij klawisz `w` w oknie terminala lub wpisz bezpośrednio `npx expo start --web`.
* **Smartfon (Android / iOS):** Zeskanuj kod QR wyświetlony w terminalu przy użyciu aplikacji **Expo Go** (urządzenie mobilne i komputer muszą być w tej samej sieci Wi-Fi).

---

## Dokumentacja

Szczegółowy opis założeń projektowych, przypadki użycia oraz zakres funkcjonalny znajdują się w dedykowanym dokumencie:
* [Pełna dokumentacja projektu](docs/topic-selection.md)
