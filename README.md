# Smart-Car-Interface

Projekt realizowany w ramach przedmiotu TWwAIRII.

Aplikacja kliencka systemu telemetrii i zdalnego sterowania pojazdem Opel Corsa B.

## Wymagania wstępne
* [Node.js](https://nodejs.org/) (wersja 18 LTS lub nowsza)
* Menedżer pakietów `npm` lub `yarn`
* *(Dla urządzeń mobilnych)*: Aplikacja **Expo Go** zainstalowana na smartfonie (dostępna w Google Play i App Store)

## Instalacja projektu lokalnie

1. Sklonuj repozytorium na dysk:
   ```bash
   git clone <URL_REPOZYTORIUM>
   cd CorsaOS
   ```

2. Zainstaluj zależności:
   ```bash
   npm install
   ```

## Uruchomienie aplikacji

Uruchom lokalny serwer developerski Metro:

```bash
npx expo start
```

### Opcje podglądu:
* **Przeglądarka WWW (PC/Desktop):** wciśnij klawisz `w` w terminalu lub przejdź pod adres `http://localhost:8081`.
* **Smartfon (Android/iOS):** zeskanuj kod QR wyświetlony w terminalu za pomocą aplikacji **Expo Go** (telefon musi znajdować się w tej samej sieci Wi-Fi).
* **Emulator Android:** wciśnij klawisz `a` w terminalu (wymaga skonfigurowanego Android Studio).
