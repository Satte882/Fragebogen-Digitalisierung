# Hinweise für Coding-Assistenten

Dieses **öffentliche** Repository beschreibt einen neutralen Form-Digitizer-Piloten.

## Verbindliche Leitplanken

- **Keine Unternehmensbezüge**, keine nichtöffentlichen Formularvorlagen, keine realen Kunden- oder Personendaten.
- Niemals geheime Schlüssel, Zugangsdaten, Session-Secrets, Uploads, Ergebnis-CSV oder Rohbilder committen.
- Architektur und UX zuerst gegen README und docs/MVP.md abgleichen; bei Änderungen die Spezifikation aktualisieren.
- **Ein Formularlayout**, 5 Fragen mit Antwortwerten 1–4 und ca. 4–5 Zeilen handschriftlichem Freitext.
- Batch-Upload von Bildern, bearbeitbarer Vorgangsname, stabile Vorgangs-/Bild-IDs.
- Dreispalten-Prüfung: Originalbild, unveränderter Modellvorschlag, final bestätigtes Ergebnis.
- Kein „100 % sicher“ bei grünen Fällen; Unsicherheiten sichtbar und manuell prüfbar halten.
- Keine fehlenden Antworten erfinden. Antworten im Status no_answer/multiple/unreadable werden nicht als Zahlen geraten.
- Originalfreitext transkribieren, dann ins Deutsche übersetzen, keine Glättung/Interpretation.
- **Export nur finaler Werte** – keinerlei doppelte KI-Roh-Antwort in CSV.
- Admin und gemeinsame Testrolle haben denselben fachlichen Funktionsumfang; Admin verwaltet nur zusätzlich technische Einstellungen.
- Gleiches Testlogin darf **keine gemeinsamen Arbeitsdaten** implizieren. Sitzungsisolation immer serverseitig erzwingen.
- Externe Modell-API ist nicht lokal. Für Pilotaufrufe nur selbst erstellte/synthetische Bilder verwenden.
- Kein externes Deployment vor funktionierenden Auth-, Session-, Upload- und Security-Tests.
- Leichte, testbare Python-/FastAPI-Implementierung bevorzugen; keine unnötige Datenbank oder Microservices.

## Wichtige Dokumente

- docs/MVP.md – verbindliche fachliche Anforderungen.
- docs/DATA_CONTRACT.md – Felder und CSV-Ausgabe.
- docs/ARCHITECTURE.md – technische Leitplanken.
- docs/TEST_PLAN.md – Qualitätsnachweis.
- docs/ROADMAP.md – Reihenfolge.

## Arbeitsweise

Erst Tests und klare Statuskontrakte, dann Model-Adapter und UI verbinden. Anbieterabhängige Schnittstellen kapseln. Synthetische Ground Truth statt unüberprüfter Modell-Selbstaussagen nutzen. Keine Funktion als „implementiert“ dokumentieren, bevor sie tatsächlich getestet ist.
