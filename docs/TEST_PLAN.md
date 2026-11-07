# Test- und Evaluationsplan

**Zweck:** Messbar belegen, was die Digitalisierung tatsächlich korrekt erfasst – und was menschlich geprüft oder korrigiert werden musste.

## Testdatengrundlage

Nur **selbst erstellte, synthetische** Formulare mit zuvor dokumentierten Sollwerten. Keine echten Kundendaten. Neutrale Namen und Beispielkommentare.

Startmenge: **10 verschiedene Fotoaufnahmen** desselben Formularlayouts:

1. Vollständiger, gut lesbarer Bogen.
2. Zweiter klar ausgefüllter Bogen mit anderen Werten.
3. Eine leere Bewertungsfrage (Status no_answer).
4. Zwei Kreuze bei einer Frage (Status multiple).
5. Kreuz unscharf/zwischen Optionen (Status unreadable).
6. Leeres Freitextfeld.
7. Handschriftlicher deutscher Freitext.
8. Handschriftlicher englischer Freitext mit deutscher Übersetzung.
9. Handschriftlicher Freitext einer weiteren Sprache mit deutscher Übersetzung.
10. Schräg fotografiertes oder schlechter beleuchtetes Blatt, ggf. technischer Fehler.

Jedes Testbild erhält einen separaten synthetischen **Ground-Truth-Datensatz**. Wo die Quelle selbst unleserlich ist, wird **unreadable** als Sollwert definiert – kein erfundener „richtiger“ Wert.

## Zu prüfen

### Datenerkennung

- Vergleich der fünf Q-Werte und Feldstatus mit Ground Truth.
- **Exakte Trefferquote je Skalenfeld**, separat von der Gesamtformularquote.
- **False-Green-Rate:** Fälle mit grüner Freigabeempfehlung, die dennoch falsch erkannt wurden. Besonders kritisch.
- Korrekte Erkennung von **no_answer**, **multiple** und **unreadable**; nicht als identische Fehler zählen.
- Fotoweise Ausfallrate (API-/Bild-/Parserfehler) und Möglichkeit zum Wiederholen.

### Freitext

- Originalsprachliche Transkription anhand der Quelle bewerten.
- Deutsche Übersetzung separat auf **Bedeutungstreue, Vollständigkeit und unzulässige Ergänzungen** prüfen.
- Unterschiede zwischen reiner Zeichenerkennung und Übersetzungsfehlern erkennbar machen.
- Für einsprachige klare Fälle zusätzliche Zeichen-/Wortfehlerrate möglich; bei Freitext verschiedener Sprachen nicht nur eine aggregierte Metrik berichten.

### Interaktion und Isolation

- 10 Fotos per Ordnerimport, bearbeitbarer Vorgangsname, stabile Zuordnung von Bildnummern/Dateinamen.
- Grün: rechte Spalte vorausgefüllt, finale Übernahme ohne Korrektur möglich.
- Gelb: Problemfeld markiert, „Manuell prüfen“ aktiviert Bearbeitung und finale Bestätigung.
- Jedes Bild zeigt Original, unbearbeitete KI-Erkennung und final bestätigtes Ergebnis.
- Export enthält **nur** bestätigte Datensätze, keine Rohdaten; kein stilles Weglassen ohne UI-Hinweis.
- Zwei parallele Sitzungen mit **demselben Testlogin** dürfen gegenseitig **keine** Bilder, Ergebnisse oder CSVs lesen/verändern.
- Admin kann technische Einstellungen ändern, Testrolle nicht (auch nicht über API-Aufrufe).
- Logout, Sessionablauf, Bildlimit, ungültige Dateiformate, fehlender API-Key und API-Timeout kontrolliert abfangen.

## Pilot-Auswertung

Nicht „100 % sicher erkannt“ berichten. Stattdessen getrennt ausweisen:

- Fotoanzahl und verarbeitete Formulare.
- Anteil der Bewertungsfelder mit **exaktem Treffer gegen Ground Truth**.
- Anteil der Fälle, die als **übernahmebereit** empfohlen wurden und tatsächlich korrekt waren.
- Anzahl ohne Korrektur bestätigter vs. manuell korrigierter Formulare.
- Freitext-Transkriptions- und Übersetzungsfehler.
- Laufzeit und API-Kosten je Vorgang (ohne vertrauliche Payloads zu loggen).

Beispiel für eine **Darstellung**, nicht als behauptetes Ergebnis: „10 verarbeitet; 8 ohne Korrektur bestätigt; 2 korrigiert; 0 offen.“ Zahlen dürfen erst nach echtem Test als Messung erscheinen.

## Abnahmekriterien für die erste Demo

1. Die gesamte Eingabe–Erkennung–Prüfung–CSV-Kette funktioniert mit den Testfällen.
2. Keine unerkannten oder ungültigen Feldstatus werden unbemerkt als gültige Skalenwerte exportiert.
3. Feldstatus „keine Antwort“ wird nie als Wert 0 oder geratenes Kreuz exportiert.
4. Fehlende/verzerrte Bilddaten führen zu erkennbarem Prüf- oder Fehlerstatus.
5. Die Testrolle kann die End-to-End-Funktionen ausführen, technische Einstellungen aber nicht ändern.
6. Keine gegenseitige Datenlesbarkeit zwischen Test-Sitzungen.
7. Nach Ablauf eines Arbeitsbereichs kommuniziert die UI verständlich, dass nicht exportierte Ergebnisse verloren sein können.

## Handschrift-Beispiele

Die fünf freigegebenen, fiktiven Testbögen sind in app/example_forms versioniert. Die Originaldateien unter local-data bleiben lokal. Die veröffentlichten PNGs behalten die Bildpixel und enthalten keine übernommenen Dateimetadaten. Die leere Vorlage zählt nicht zum Testset.

Die manuell geprüften Feldzustände stehen in handwriting-ground-truth.json. Die Dateien mit Sollwerten werden ausschließlich zur Auswertung benutzt. Der Modelladapter bekommt nur das normalisierte Bild und den allgemeinen Erkennungsprompt. Der genaue Wortlaut des dritten Bogens wird wegen unsicherer Lesart nicht gewertet. Die Übersetzungs- und Transkriptionsmetriken prüfen exakte Textgleichheit. Zeichensetzung und zulässige Übersetzungsvarianten können deshalb als Abweichungen zählen.

Für einen vollständigen Vergleich alle fünf Bögen im selben Beispieldatensatz verarbeiten, bei Bedarf korrigieren und bestätigen. Die private JSON-Auswertung der aktiven Sitzung steht unter /api/batches/{batch_id}/evaluation und enthält unveränderte Erkennung und den aktuell bestätigten Datensatz. Nach dem Speichern der Antwort in local-data/handwriting-evaluation.json lässt sich der Vergleich lokal ausführen:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_quality docs/handwriting-ground-truth.json local-data/handwriting-evaluation.json
```

Die Auswertung verknüpft über den stabilen Beispiel-Dateinamen. Sitzungs- und Bild-IDs bleiben für jeden Vorgang individuell. Die Ergebnis-CSV enthält weiterhin nur die bestätigten Werte und ihre bestehenden Zuordnungsfelder.
