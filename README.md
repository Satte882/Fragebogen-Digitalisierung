# Form Digitizer – Fragebogen-Digitalisierung

**Status:** Konzept und MVP-Spezifikation (Stand: 07.11.2026). **Noch keine lauffähige Anwendung.**

Ein unabhängiger, neutraler Machbarkeitsprototyp: Fotografierte Papierfragebögen werden mit einem multimodalen KI-Modell gelesen, von Menschen bei Bedarf überprüft und als **strukturierte CSV-Daten** ausgegeben. Die Anwendung **digitalisiert und übersetzt**, führt aber **keine inhaltliche Auswertung der Antworten** durch.

> **Hinweis für die Benutzeroberfläche:** „Diese Anwendung digitalisiert Fragebögen und übersetzt Freitexte ins Deutsche. Eine inhaltliche Analyse oder Bewertung der Kundenantworten findet nicht statt.“

## Ziele und Grenzen

- **Eingabe:** Ein fester, neutraler Fragebogentyp; **5 Fragen mit Werten 1–4**, dazu **4–5 Zeilen handschriftlicher Freitext**. Mehrere Fotos können gemeinsam hochgeladen werden, bevorzugt per Ordnerauswahl im Browser.
- **Vorgänge:** Ordnername wird als Vorgangsname vorgeschlagen, ist bearbeitbar und wird um eine stabile Vorgangs-ID ergänzt. Alle Bilder sind einem Vorgang zugeordnet.
- **KI:** Multimodales Gemini-Modell **über OpenRouter** als erster Adapter; später austauschbar gegen einen anderen API-Adapter. API-Verarbeitung ist **nicht lokal**: Bilder werden an den Modellanbieter übertragen. Test ausschließlich mit eigens erstellten/synthetischen Inhalten.
- **Prüfung:** Dreispaltenansicht **Originalbild | KI-Roh-Erkennung | bestätigtes Ergebnis**. Bei plausiblen Fällen rechts vorausfüllen, bei Unklarheiten „Manuell prüfen“; anschließend „Final übernehmen“. Bilder und Felder bleiben kontrollierbar.
- **Freitext:** Originalgetreue Transkription und zusätzlich **Übersetzung nach Deutsch**, **keine Glättung**, keine Sentimentanalyse oder Zusammenfassung.
- **Kreuze:** Eindeutig fehlende Antwort = „Keine Antwort“; unsichere, mehrfache oder nicht lesbare Markierung = gesonderter Status. Keine Antworten erfinden oder vom Prüfer ergänzen.
- **Export:** **CSV nur mit final bestätigten Angaben**, Vorgangszuordnung und Status. Die KI-Roh-Erkennung wird **nicht** mitexportiert.
- **Rollen:** **Admin** und gemeinsamer **Testzugang** dürfen beide sämtliche Fachfunktionen einschließlich Korrektur und CSV-Export ausführen. Nur der Admin darf technische Einstellungen verwalten. **Jede Anmeldung bekommt einen isolierten Arbeitsbereich**, auch bei gemeinsamem Testlogin.
- **Betrieb:** Erst lokal auf Windows, später optional als Demo auf Render. Ohne dauerhafte Datenbank; ein abgelaufener Arbeitsbereich kann nicht wiederhergestellt werden. Zugleich gibt es neutrale, fest bereitgestellte Demodaten für eine Vorführung.

## Fachlicher Ablauf

1. Anmelden (Admin oder Test).
2. Fotoordner oder mehrere Bilddateien auswählen; bearbeitbaren Vorgangsnamen bestätigen.
3. Bilder einzeln an das gewählte multimodale Modell übermitteln und Ergebnisse **strukturiert** erhalten.
4. Pro Bild/Pflichtfeld Ergebnisse und Auffälligkeiten anzeigen. **Grün = definierte technische Prüfregeln bestanden, niemals „100 % korrekt“**; Gelb = Prüfung erforderlich.
5. In der Dreispaltenansicht das Bild gegen Roh-Erkennung und endgültigen Datensatz vergleichen; bei Bedarf korrigieren und **final bestätigen**.
6. Statusübersicht („ohne Korrektur übernommen“, „manuell korrigiert“, „noch offen“) und Download der **CSV mit ausschließlich finalen Datensätzen**.

## Geplante technische Basis

- Python + FastAPI, einfache serverseitig angebundene Weboberfläche.
- Adapter-Schnittstelle für OpenRouter/Gemini und einen späteren alternativen Modell-Endpunkt.
- Valider, versionierter JSON-Zwischendatensatz; regelbasierte Feldvalidierung.
- Serverseitige Authentifizierung, kurzlebige isolierte Sitzungen, kein dauerhafter Bildspeicher im MVP.
- Für die Qualitätsevaluation: Roh-Erkennung und Korrektur **nur innerhalb des jeweiligen Arbeitsbereichs** vergleichbar, nicht Teil des CSV-Exports.
- CSV-Export UTF-8 mit BOM zur problemlosen Anzeige deutscher Texte in Excel.

## Projektdokumentation

| Dokument | Inhalt |
| --- | --- |
| [MVP-Anforderungen](docs/MVP.md) | Funktionen, Rollen, Bedienablauf und Abnahmekriterien |
| [Technisches Konzept](docs/ARCHITECTURE.md) | Architektur, Modelladapter, Sitzungen, Sicherheit, Deployment |
| [Datenvertrag und CSV](docs/DATA_CONTRACT.md) | Feldstatus, JSON-Zwischenmodell, Exportregeln |
| [Test- und Evaluationsplan](docs/TEST_PLAN.md) | Qualität und reproduzierbarer Machbarkeitsnachweis |
| [Umsetzungsplan](docs/ROADMAP.md) | Schrittfolge und bewusst ausgeschlossener Umfang |
| [Neutraler Musterfragebogen](examples/musterfragebogen.html) | Druckbare, eigens erstellte Formularvorlage |

## Öffentliche Repository-Regeln

Dieses Repository enthält **keine realen Kundendaten, keine fremden internen Formulare, keine Zugangsdaten und keine API-Schlüssel**. Keine Fotos, hochgeladenen Formulare oder CSV-Ergebnisse committen. API-Schlüssel gehören in lokale Umgebungsvariablen bzw. in die Secret-Verwaltung des Hostinganbieters.

**Wichtig:** Das Repository enthält derzeit **Anforderungen und eine Formularvorlage**, aber noch keinen funktionierenden Upload-, Login- oder Erkennungsdienst. Das erste Ziel ist ein überprüfbarer MVP – keine Produktivsoftware.
