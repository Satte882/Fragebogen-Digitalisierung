# Umsetzungsplan – neutraler Machbarkeitsprototyp

**Status:** Phase 0 dokumentiert; Implementierung noch nicht gestartet.

## Phase 0 – Projektgrundlage (dokumentiert)

- [x] Ziel und bewusste Grenzen festhalten.
- [x] Nutzerfluss für Ordnerimport, Prüfung und CSV beschreiben.
- [x] Rolle Admin versus gemeinsamer Testzugang mit Sitzungsisolation definieren.
- [x] JSON-/CSV-Vertrag definieren.
- [x] Eigene neutrale Musterformularvorlage vorbereiten.
- [x] Testplan und Sicherheitsanforderungen dokumentieren.

## Phase 1 – Lokaler funktionsfähiger Kern

- [ ] Python-/FastAPI-Projektstruktur, Qualitätswerkzeuge und automatisierte Tests einrichten.
- [ ] Benutzeroberfläche für Vorgänge, Mehrfach-/Ordnerupload und Bildübersicht aufbauen.
- [ ] Fünf-Fragen-Schema, Freitext und Validierungslogik mit synthetischen Fällen testen.
- [ ] **Mock-Modelladapter** und neutrale vorgefertigte Demodaten einbauen, damit UI-Tests ohne API-Kosten möglich sind.
- [ ] Gemini über **OpenRouter** integrieren; API-Key nur serverseitig.
- [ ] JPEG/PNG erkennen und strukturierte KI-Ausgaben parsen, Fehler sauber behandeln.
- [ ] Dreispaltenansicht mit grün/gelb, Feldmarkierung, Editieren und finaler Bestätigung umsetzen.
- [ ] Deutsche Übersetzung anzeigen, ohne Originaltext zu verändern oder sprachlich zu glätten.
- [ ] CSV nur mit bestätigten Ergebnissen; UTF-8/BOM, Semikolon, Schutz vor Formelinterpretation.
- [ ] Funktionale Tests mit 10 synthetischen Fotoaufnahmen.

**Ergebnis:** Lokal demonstrierbare Digitalisierung inklusive Qualitätsprüfung und Export.

## Phase 2 – Gesicherte Online-Demo

- [ ] Zwei Rollen mit Passwort-Hash/Secret-Konfiguration einrichten; keine Demo-Defaults offen im Code.
- [ ] Gemeinsamer Testlogin mit **je Anmeldung isolierter** Sitzung; Admin separat.
- [ ] Rollenrechte **serverseitig** prüfen; Testrolle hat alle Fachfunktionen, aber keine Admin-Einstellungen.
- [ ] Upload- und API-Kostenlimits, Zeitlimits, Datenablauf, Logout und Fehlerbehandlung ergänzen.
- [ ] Isolations-, Auth-, CSV- und Sicherheitstests vor Freigabe durchführen.
- [ ] Render-Webservice aufsetzen (optional kostenlos; Dienst kann schlafen, lokale Daten sind flüchtig).
- [ ] Synthetische Demo-Fixdaten bereithalten; ausschließlich synthetische Bilder im Test.
- [ ] Komplette End-to-End-Demo mit dem freigegebenen Testzugang ausführen.

**Ergebnis:** Geschützter Pilotlink für eingeladene Personen, keine produktive Datenablage.

## Phase 3 – Nur bei erfolgreicher Pilotbewertung

- [ ] Modellwechsel auf eine alternative **kompatible API** testen und Qualität neu messen.
- [ ] Weitere Formularlayouts nur bei echtem Bedarf.
- [ ] Optionales persistentes Speichern, Benutzerkonten, Audit-Trail und Datenbankintegration nach separater Datenschutz-/Sicherheitsprüfung.
- [ ] Datenschutz- und Sicherheitskonzept für reale Daten **neu bewerten**; Pilot-Vorgaben reichen dafür nicht aus.

## Definition of Done pro Änderung

Funktion und Fehlermeldungen nachvollziehbar; keine Geheimnisse und echten Nutzerdaten im Git-Repo; Zugriffsrechte erzwungen; Tests grün; Daten- und CSV-Vertrag eingehalten; neue Entscheidungen in README/Dokumentation nachgeführt.

## Nicht jetzt

Keine Produktionsinstallation, keine echte Kundendatenverarbeitung, keine permanente Benutzerverwaltung, kein Reporting/Sentiment, keine unsichere Freigabe aufgrund einer Modell-„Konfidenz“.
