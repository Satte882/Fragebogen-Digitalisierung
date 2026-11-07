# Roadmap – tatsächlicher Stand (07.11.2026)

## Umgesetzt (MVP-Code)

- [x] Projektgrundlage, neutraler Musterfragebogen, Daten- und CSV-Vertrag.
- [x] FastAPI, Upload per Bild oder Ordner, Vorgangs- und Bildzuordnung.
- [x] OpenRouter/Gemini-Adapter, Mock-Adapter ohne API-Kosten, synthetische Demo.
- [x] Fünf Antworten und Freitext inklusive Originaltranskription und deutscher Übersetzung.
- [x] Drei Spalten, grün/gelb, menschliche Korrektur/Bestätigung, erneutes Öffnen.
- [x] CSV ausschließlich mit bestätigten Werten, ohne KI-Rohdaten.
- [x] Administrator/Testlogin, gleiche Fachfunktionen, isolierte Sitzungen.
- [x] Automatisierte API-, Schema-, Rollen-, CSV- und OpenRouter-Simulationstests.
- [x] Render-Konfiguration und lokaler Secret-Bootstrap.

- [x] Serverlauf für 30 Bögen, Ausnahmenliste, Stichprobe, getrennte Bestätigungsherkunft und Teil-Export-Warnung.
- [x] Reproduzierbare Offline-Auswertung gegen Sollwerte mit eigener Datendatei.

## Vor echtem Pilotbetrieb noch prüfen

- [ ] Tatsächlich verfügbare Gemini-ID mit einem echten OpenRouter-Key testen.
- [ ] Handschrift-/Kreuz-Erkennung anhand 10 selbst ausgefüllter und fotografierter Testbögen gegen Ground Truth messen.
- [x] Zentrale UI-Abläufe unter Windows in Edge inklusive schmaler Ansicht geprüft ([Abnahmebericht](LOCAL_VERIFICATION.md)).
- [ ] Render mit privaten Secrets bereitstellen und zwei parallele Testanmeldungen prüfen.
- [ ] API-Kostengrenzen und Render-Free-Restart real ausprobieren.

## Später optional

- [ ] Austauschadapter für einen alternativen internen KI-Endpunkt, Qualität getrennt testen.
- [ ] Wiederaufnahme, Datenbank, dauerhafte Speicherung, weitere Layouts.
- [ ] Revisions-/Sicherheits-/Datenschutzkonzept für reale Daten.

**Keine Produktivfreigabe.** Grün bedeutet technische Prüfregeln bestanden, nicht absolute Korrektheit.
