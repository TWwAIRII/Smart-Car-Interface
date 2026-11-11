# Przypadki Użycia: Smart Car Mobile Interface (Aplikacja na Smartfon)

## 1. Wykaz Aktorów

### Aktorzy Główni (Ludzie)
* **Kierowca / Użytkownik Smartfona:** Osoba zarządzająca pojazdem i nawigująca z poziomu aplikacji mobilnej na telefonie.

### Aktorzy Pomocniczy (Systemy zewnętrzne i sprzęt)
* **Moduł Telematyczny Pojazdu / CAN Bus:** Sprzęt w aucie przesyłający dane telemetryczne (bateria/paliwo, zamki, lokalizacja, usterki) przez Cellular do telefonu lub chmury.
* **Chmura Producenta (Cloud Back-end):** Serwer pośredniczący w komunikacji zdalnej, autoryzacji oraz przechowywaniu danych o pojeździe.
* **Zewnętrzne API Map i Nawigacji:** Serwisy dostarczające mapy, ruch drogowy oraz bazę stacji ładowania/paliw bezpośrednio do aplikacji mobilnej.

---

## 2. Szczegółowy Opis Przypadków Użycia

### UC1: Zdalne sterowanie klimatyzacją i schładzanie/ogrzewanie
* **Główny Aktor:** Kierowca (Smartfon)
* **Aktorzy Wspierający:** Chmura Producenta, Moduł Telematyczny Pojazdu
* **Główny Scenariusz:**
  1. Użytkownik otwiera aplikację w telefonie będąc poza pojazdem (np. w domu).
  2. Ustawia docelową temperaturę i klika "Uruchom ogrzewanie/klimatyzację".
  3. Aplikacja wysyła żądanie do Chmury Producenta, która przekazuje polecenie do samochodu.
  4. Samochód uruchamia układ klimatyzacji, a aplikacja na żywo podaje aktualną temperaturę we wnętrzu.

### UC2: Podgląd stanu pojazdu i telemetria na żywo
* **Główny Aktor:** Kierowca (Smartfon)
* **Aktorzy Wspierający:** Moduł CAN Bus / OBD
* **Główny Scenariusz:**
  1. Podczas jazdy lub postoju aplikacja pobiera dane z modułu pojazdu.
  2. Na ekranie telefonu wyświetlane są w czasie rzeczywistym parametry: prędkość, poziom baterii/paliwa, ciśnienie w oponach, szacowany zasięg.
  3. Po zakończeniu jazdy dane są zapisywane w podsumowaniu trasy.

### UC3: Otrzymywanie powiadomień Push o zdarzeniach
* **Główny Aktor:** Kierowca (Smartfon)
* **Aktorzy Wspierający:** Moduł Telematyczny Pojazdu, Chmura Producenta
* **Główny Scenariusz:**
  1. W samochodzie dochodzi do zdarzenia (np. wzbudzenie alarmu, spadek ciśnienia w oponie, stan baku poniżej 15%).
  2. Pojazd wysyła alert do Chmury.
  3. Smartfon użytkownika wyświetla natychmiastowe powiadomienie Push z opisem zdarzenia i sugerowaną reakcją.

### UC4: Zdalne lokalizowanie zaparkowanego pojazdu
* **Główny Aktor:** Kierowca (Smartfon)
* **Aktorzy Wspierający:** API Map / GPS, Moduł Telematyczny Pojazdu
* **Główny Scenariusz:**
  1. Użytkownik szuka swojego auta na dużym parking lub w nowym mieście.
  2. Otwiera aplikację i wybiera opcję "Znajdź auto".
  3. Aplikacja pokazuje na mapie pozycję samochodu oraz pieszą trasę doprowadzającą.
  4. Użytkownik z poziomu telefonu może wywołać sygnał dźwiękowy (klakson) lub błyśnięcie świateł, by łatwiej dostrzec pojazd.

### UC5: Podgląd historii tras i statystyk zużycia
* **Główny Aktor:** Kierowca (Smartfon)
* **Aktorzy Wspierający:** Chmura Producenta
* **Główny Scenariusz:**
  1. Użytkownik wybiera zakładkę "Historia" w aplikacji mobilnej.
  2. Aplikacja wyświetla listę przebytych tras, średnie zużycie energii/paliwa, koszty przejazdów oraz styl jazdy (ecodriving).
