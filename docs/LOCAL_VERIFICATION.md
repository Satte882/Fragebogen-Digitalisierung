# Lokale technische Abnahme

**Datum:** 7. November 2026 · **Basis:** `473695df3735cc602e2dd60ef773b666fa59d7d5` (`origin/main`) · **Korrekturen:** lokaler Branch `local/mvp-verification`.

## Nachprüfung der Mehrfachmarkierungs-Auswahl

Die Sonderregel aus der folgenden Abnahme wurde durch eine einheitliche Bedienung ersetzt. Auch bei synthetischen Bögen lassen sich die Werte 1 bis 4 auswählen. Bei einem Wechsel von Mehrfachmarkierung zu einem Einzelwert ist die schriftliche Begründung freiwillig. Eine ausdrückliche Belegbestätigung bleibt erforderlich. Eine ausgefüllte Begründung bleibt im Prüfprotokoll erhalten. Bei mehreren gültigen Kreuzen bleibt die Mehrfachmarkierung die fachlich richtige Eingabe. Die Anwendung prüft den Sichtbeleg nicht automatisch.

## Korrekturübersicht und Mehrfachmarkierungen (vor der Nachprüfung)

**Basis:** `88310c9` · Lokale Abnahmeinstanz im Mock-Modus: http://127.0.0.1:8010.

- Nach Abschluss zeigt „Wie die Bögen bestätigt wurden“ Sammelübernahmen, Einzelprüfungen, unveränderte Einzelprüfungen und korrigierte Bögen. Einzelprüfungen umfassen auch individuell geprüfte Stichproben.
- „Korrekturen anzeigen“ listet Bildnummer, Feld, ursprünglichen Vorschlag und aktuell bestätigten Wert. Auch ein geänderter Freitextstatus ist nachvollziehbar. Wird eine Korrektur nach Wiederöffnung zurückgenommen, verschwindet sie aus der aktuellen Übersicht. Die interne Historie bleibt erhalten.
- **Bild 30, Frage 4:** Im synthetischen Original sind die Optionen 2 und 3 markiert. Edge zeigte „Mehrfachmarkierung“ und sperrte Einzelwerte. Auch ein gezielt gesendeter API-Request mit Wert 3, Belegbestätigung und Begründung erhielt HTTP 422. Der CSV-Wert bleibt leer, der Feldstatus lautet `multiple`.
- Bei regulären Uploads verlangt die Auflösung einer Mehrfachmarkierung zu einem Einzelwert eine feldbezogene Begründung und eine ausdrückliche Belegbestätigung. Ein kontrollierter Test mit genau einem sichtbaren Kreuz und einem absichtlich falschen Modellvorschlag prüft die zulässige Korrektur. Die Anwendung verifiziert die Erklärung bei Uploads nicht am Bild.
- Die Ergebnis-CSV verwendet dieselben Spalten und dieselbe Exportlogik wie zuvor. Rohantwort, Begründung und Historie bleiben intern. Ein separater Protokollexport wurde nicht ergänzt.

**Abnahme:** 43 automatisierte Tests. In Edge zeigte der 30er-Demovorgang 26 Sammelübernahmen, vier unveränderte Einzelprüfungen und null Korrekturen. In einem getrennten synthetischen Upload wurde ein Bogen korrigiert und die Vorher-Nachher-Anzeige bei 1440 und 480 Pixeln Breite betrachtet. Keine externen Modellaufrufe.


## Abnahme des finalen Arbeitsablaufs

**Basis:** `7b59c00` · **Implementierung:** `4848710` · **Branch:** `codex/final-ux-workflow`. Lokale Abnahmeinstanz im Mock-Modus unter http://127.0.0.1:8009.

| Schritt | Umsetzung und Nachweis |
| --- | --- |
| Bögen erfassen | Ein Klick auf „Neue Batch-Demo · 30 Bögen“ öffnet den neuen Vorgang mit 26 übernahmebereiten und vier offenen Festfällen. Edge prüfte auch zwei unmittelbar aufeinanderfolgende Klicks und beobachtete genau einen Erstellungsaufruf. Die Kurzdemo mit drei Bögen funktionierte in derselben Sitzung. Reguläre Uploads behalten die serverseitige Erfassung. |
| Ausnahmen prüfen | „Zu prüfen (4)“ ist voreingestellt und kein Bogen wird automatisch geöffnet. „Alle (30)“ scrollt vertikal und „Übernahmebereit (26)“ bleibt für freiwillige Prüfung erreichbar. Die Qualitätskontrolle schlägt bis zu fünf Bögen vor und blockiert die Sammelbestätigung nicht. |
| Korrektur speichern | Die rechte Spalte ist bei gelben Fällen sofort editierbar. Bei Bild 27 erhielt Frage 4 den Fokus und die Originalstelle wurde markiert. Edge prüfte Zoom, Belegfehler am Kontrollfeld und einen beim Ansichtswechsel erhaltenen Entwurf. Ein zurückgesetzter Wert zeigt keinen Korrekturhinweis. Vier Speicheraktionen öffneten nacheinander die nächsten Fälle und am Ende die Übersicht, ohne Speicherdialoge. |
| Gesammelt bestätigen | Die Karte steht direkt unter der Prüfliste. Mit offenen Fällen ist sie zweitrangig. Nach den vier Einzelprüfungen wird sie hervorgehoben. Ein Klick bestätigte die übrigen 26 ohne zusätzliches Modal. Die Herkunft blieb als 26 Sammelbestätigungen und vier Einzelprüfungen unterscheidbar. |
| Exportieren | Bei vier bestätigten Bögen meldete der Teil-Export 26 fehlende Bögen. Nach der Sammelbestätigung zeigte die Anwendung „30 von 30 Bögen abgeschlossen“. Edge lud die vollständige CSV mit 30 Zeilen ohne Rückfrage herunter. Rohtranskription und Belegprotokoll erschienen nicht in der CSV. |
| Erkennung und Schutz | Erkannte Antworten, handschriftlicher Originaltext und deutsche Übersetzung sind getrennt. Die unveränderte JSON-Antwort ist unter „Technische Details“ zugänglich. Rollen und Sitzungsisolation wurden erneut geprüft. Die bestehende serverseitige Belegprüfung und die Kostenlimits bleiben Teil der Testsuite. |

**Automatisiert:** 41 Tests bestanden. Python-Kompilierung, JavaScript-Syntax und Git-Diff-Prüfung liefen erfolgreich. Eine bekannte Starlette-Testclient-Warnung bleibt bestehen.

**Sichtprüfung in Microsoft Edge:** 1920 × 1080 für Einstieg, Sammelbestätigung und Export, 1366 × 768 für die Dreispaltenprüfung und 480 Pixel Breite für das mobile Ergebnisformular. Die gerenderten Aufnahmen wurden betrachtet. Ein in der ersten Sichtprüfung sichtbarer Korrekturhinweis nach dem Zurücksetzen einer Eingabe wurde entfernt und der Fall erneut getestet.


**Grenzen:** Die Demo verwendet vorbereitete Ergebnisse. Für echte Handschrift und schwierige Aufnahmen fehlt weiterhin eine belastbare Qualitätsmessung. Entwürfe bleiben beim Wechsel innerhalb des Tabs erhalten. Beim Neuladen oder Schließen warnt der Browser, sofern er eine Warnung zulässt. Sitzungsablauf und Serverneustart können nicht exportierte Daten verwerfen. Kein Push, kein Deployment und keine kostenpflichtigen Modellaufrufe in diesem Auftrag.

## Abnahme der vereinfachten Prüfwarteschlange

**Basis:** `382b2ea` · **Implementierung:** `00628d9` · **Branch:** `codex/review-queue-integrity`. Lokale Abnahmeinstanz im Mock-Modus: http://127.0.0.1:8008. Über **Demo-Werkzeuge → Batch-Demo · 30 Bögen → Vorgang verarbeiten** lässt sich der Ablauf ohne Anbieteraufrufe nachstellen.

| Bereich | Umsetzung und Nachweis |
| --- | --- |
| Einstieg und Bildnavigation | Nach dem Batch-Lauf öffnet sich die Übersicht ohne Bild 1. Edge zeigte vier offene Fälle. „Alle“ zeigte 30 Bögen, „Übernahmebereit“ 26. Die Bildliste scrollte vertikal. Die 1920er Ansicht zeigte die vier Aufgaben in zwei kompakten Reihen. |
| Direkte Prüfung und Abschluss | Bild 27 war beim Öffnen sofort editierbar. Der Prüfgrund hob die Mehrfachmarkierung in Original, Erkennung und Ergebnis hervor. Abbrechen im Speicherdialog hielt den Fall offen. Nach den vier Bestätigungen führte die App zurück zur Übersicht. Anschließend bestätigte Edge die übrigen 26 in einer Aktion. |
| Datenintegrität | Edge blockierte einen Versuch, ein leeres Feld ohne Beleg zu füllen. Alle vier leeren Antworten blieben leer. Bei einem separat hochgeladenen synthetischen Bild wurde ein sichtbar angekreuzter Wert erfasst. Eine weitere Änderung setzte die Checkbox zurück. Die API-Regressionen decken fehlend, mehrfach, unlesbar und Zahl-zu-Zahl ab und prüfen unveränderte Rohdaten sowie das interne Änderungsprotokoll. Die Erklärung stammt vom Prüfer. Sie ist keine automatische Bildprüfung. |
| Navigation und Meldungen | Kopfzeile auf Produktname und Modus reduziert. Neuer Vorgang und Demo-Werkzeuge sind getrennt. Das Benutzermenü zeigt Sitzungsinformationen und Abmelden sowie für Admins die Modelleinstellungen. Edge prüfte beide Rollen. Kurze Toasts ersetzen die großen Erfolgsmeldungen. Eingabefehler stehen am jeweiligen Formular. Der Anbieterhinweis erscheint vor echten Aufrufen, ein nachträglicher Moduswechsel wird serverseitig abgefangen. |
| Vorgänge und CSV | Edge prüfte Umbenennen mit Enter und Abbruch mit Escape. Der neue Name erschien in der CSV mit genau 30 bestätigten Zeilen. Rohdaten und Belegprotokoll blieben intern. Löschen wurde erst nach Bestätigung ausgeführt und ließ den anderen Vorgang unverändert. API-Tests verhindern Löschen während laufender Verarbeitung und Zugriffe aus fremden Sitzungen. |
| Visuelle Abnahme | Edge bei 1920 × 1080, 1366 × 768 und 480 Pixeln Breite. Die gerenderten Aufnahmen wurden betrachtet. Auf Mobilgeräten lässt sich direkt zur Ergebnisspalte springen. An 1366 × 768 bleibt die dreispaltige Prüfung vertikal scrollbar. Zoom wurde mit der Tastatur geöffnet und per Escape geschlossen. |


**Tests:** 40 automatisierte Tests bestanden. Der vollständige Edge-Ablauf prüfte den 30er Vorgang, Speicher- und Löschdialoge, Umbenennen, Rollen, Zoom und CSV. Python-Kompilierung, JavaScript-Syntax und Git-Diff-Prüfung liefen erfolgreich.

**Verbleibende Grenzen:** Die Browser-Abnahme verwendete synthetische Festdaten und einen Mock-Upload. Erkennungsqualität für reale Handschrift und schwierige Fotos bleibt offen. Arbeitsdaten und Belegprotokoll liegen in der Sitzung und gehen bei Ablauf oder Neustart verloren. Kein Push, kein Deployment und keine kostenpflichtigen Modellaufrufe.

## Abnahme des 30-Bögen-Workflows

**Basis:** `7ff5a9a` · **Implementierung:** `47d2c25` · **Branch:** `codex/batch-first-ux`. Der separate Abnahme-Commit enthält diesen Bericht und die Browseraufnahmen. Die lokalen Vorarbeiten wurden vollständig übernommen.

**Lokal ausprobieren:** http://127.0.0.1:8006 → anmelden → **Batch-Demo · 30 Bögen** → **Vorgang verarbeiten**. Die App auf diesem Port läuft im Mock-Modus. Die eingebaute Batch-Demo enthält 26 technisch übernahmebereite und vier prüfpflichtige Festfälle. Auch bei aktivem OpenRouter würde diese Demo keinen Anbieteraufruf auslösen. Der unveränderte Mock für reguläre Uploads liefert keine Schein-Erkennung.

| Bereich | Umsetzung und Nachweis |
| --- | --- |
| 30 Bilder und Fortschritt | Edge lud einen lokalen Ordner mit 30 synthetischen JPEGs. Ein serverseitiger Lauf verarbeitete alle Bilder. Nach Doppelklick und Neuladen war der Lauf wieder sichtbar und erreichte 30/30. Der API-Test belegte dieselbe Lauf-ID für parallele Starts und höchstens drei Aufrufe gleichzeitig. |
| Fehler und Budget | Kontrollierte 429-, Timeout- und JSON-Fehler liefen neben den übrigen Bildern. Die ersten beiden wurden automatisch wiederholt, der JSON-Fehler nur manuell. Im API-Test wurden für 30 Bilder 33 Aufrufe gezählt, davon 30 erfolgreich, drei fehlgeschlagen und drei wiederholt. Separate Tests prüften Konfigurationsfehler, temporäre 503-Antworten und beide Budgetgrenzen. |
| Sammelübernahme und Ausnahmen | Edge bestätigte 26 grüne Bögen mit einem Dialog. Vier gelbe Bögen erschienen im Filter. Nach Bestätigung sprang die Ansicht zum nächsten Fall. Bei Bild 27 zeigte das Papier für Frage 1 den Wert 3. Der simulierte Vorschlag 2 wurde nach Belegbestätigung korrigiert. Frage 2 blieb leer. |
| Herkunft und Stichprobe | Der API-Test unterscheidet Sammelübernahme, Einzelprüfung, Stichprobe und Korrektur. Die Auswahl schlägt bis zu fünf Bögen reproduzierbar nach Bild-ID vor. Ein korrigierter Stichprobenbogen setzt das Warnmerkmal, das die Oberfläche anzeigt. Bereits geprüfte Bögen werden bei einer neuen Auswahl übersprungen. Edge zeigte fünf vorgeschlagene Stichproben und nach einer Einzelbestätigung den Stand „1 geprüft, 4 offen“. |
| CSV | Edge prüfte den Hinweis vor dem Download von 26 aus 30 und danach den vollständigen Download ohne Rückfrage. Der API-Test las 30 CSV-Datensätze inklusive leerer Werte, Feldstatus und unveränderter Rohantwort. Bestehende Vertragstests prüfen Spaltenreihenfolge, BOM und Formelschutz. |
| Sitzung und Sicherheit | Zwei Testanmeldungen mit identischem Login bleiben isoliert. Start, Status und Qualitätsdaten fremder Vorgänge wurden abgewiesen. Die bestehende Suite prüft Bild-/Export-Isolation, Adminrechte, CSRF, Ablauf und Neustart. Die Oberfläche zeigt die verbleibende Zeit und warnt in den letzten zehn Minuten. Lauf und nicht exportierte Daten sind an Sitzung und Prozess gebunden. |
| Bildqualität | JPEG-Zielkante und -Qualität sind konfigurierbar, Standard jetzt 2200 Pixel und Qualität 90. Ein synthetisches Linienbild ergab bei 1800/86 ein JPEG mit 1350 × 1800 und 166.753 Byte. Bei 2200/90 waren es 1650 × 2200 und 250.712 Byte. Rotation und EXIF-Bereinigung sind getestet. Der Vergleich misst Größen und Auflösung. Eine bessere Erkennung oder Mehrkosten wurden damit nicht gemessen. |
| Qualität gegen Sollwerte | Private Live-Snapshots, Sollwertvorlage und Offline-Skript. Der kontrollierte Evaluatortest erkennt einen falsch grünen Bogen und eine korrekt ausgelöste Warnung. Die bisherige reale Gemma-Stichprobe bleibt separat ausgewiesen. Für diese Abnahme wurden ausschließlich Festdaten oder simulierte Anbieterantworten verwendet. |

**Automatisiert:** 34 Tests bestanden, außerdem Python-Kompilierung, JavaScript-Syntax und Git-Diff-Prüfung. Eine bekannte Starlette-Testclient-Warnung bleibt bestehen.

**Sichtprüfung in Edge:** 1920 × 1080, 1366 × 768 und 480 Pixel Breite. Die Aufnahmen wurden geöffnet und beurteilt. In der ersten Runde fielen ein veralteter Bestätigungszähler in der Seitenleiste und überstehende Kartenlabels auf. Beides wurde korrigiert und der Ablauf wiederholt. Die Prüfansicht lässt sich bei 1366 × 768 vertikal scrollen. Die 30 Karten bleiben in einer horizontalen Leiste. Die mobile Ansicht wurde ohne horizontales Scrollen der ganzen Seite geprüft.


**Grenzen und Abweichungen:** Das Muster mit 30 Bögen testet den Workflow, einschließlich Wiederanlauf und Ausnahmebehandlung. 50–100 tatsächlich fotografierte, handschriftliche Bögen mit unabhängigen Sollwerten sind noch nicht vorhanden. Kosten bleiben ohne belastbare Anbieterabrechnung leer. Der MVP nutzt einen Prozess. Bei Ablauf oder Neustart gehen nicht exportierte Inhalte verloren. Entwürfe im Browser-Tab überstehen keine Seitenaktualisierung. Ein wieder einlesbarer Zwischenstand, zusätzliche Tastaturkürzel und eine Messung der aktiven menschlichen Interaktionszeit wurden zurückgestellt. Die Oberfläche bleibt per Tab, Pfeiltasten in Auswahlfeldern, Enter und Maus bedienbar. Für öffentliche Last- und Betriebsfreigabe ist eine gesonderte Prüfung nötig.

Kein Push, kein Deployment und keine kostenpflichtigen Modellaufrufe in diesem Auftrag.

## Visuelle Abnahme für die CEO-Demo

**Stand zur Vorlage:** http://127.0.0.1:8003. Der ursprüngliche UX-Lauf prüfte Bedienabläufe, enthielt aber keine Sichtprüfung der gerenderten Oberfläche. Für diese Abnahme wurden Edge-Aufnahmen vor und nach dem Umbau geöffnet und auf Lesbarkeit, Hierarchie, Sichtbarkeit der Hauptaktion und Vergleichbarkeit der drei Spalten geprüft. Das ist eine visuelle Eigenprüfung ohne externen Usability-Test.


| Feedbackpunkt | Umsetzung | Test und Sichtprüfung | Visuelle Bewertung |
| --- | --- | --- | --- |
| P0 · Konkrete Prüfgründe je Frage und Freitext | Bildkarten nennen das betroffene Feld. Ein gemeinsamer Prüfhinweis erklärt den Grund über den drei Spalten. Strukturierte Modellbefunde enthalten Feld, Typ und Grund. | Edge an Bild 2 und 3. Vertragstests für strukturierte Befunde. Im Live-Fall mit Mehrfachkreuz nannte Gemma die beiden Optionen. | Der Grund ist vor dem Detailvergleich sichtbar. Die Warnbox verschiebt keine einzelne Spalte mehr. |
| P0 · Demo-Warnung von KI-Befund trennen | Bild 3 kennzeichnet den absichtlich markierten Freitext als Demo-Prüffall und weist auf fünf unauffällige Antworten hin. | Edge und Sichtprüfung an Bild 3. API-Test prüft die getrennte Kennzeichnung. | Gelb führt zur Übung, ohne einen Erkennungsfehler vorzutäuschen. |
| P1 · Visuell überarbeiten | Dunkler Rahmen, helle Prüffläche, eine klare Vorgangsüberschrift, fünf Statuskennzahlen, kompaktere Karten und eine hervorgehobene Hauptaktion. Die Ergebnisvorschau ist auch bei offenen Fällen sichtbar. | Vorher/Nachher in Edge betrachtet. Desktop mit drei Spalten, schmale Ansicht mit Direktlinks. Bedienung, Bestätigung und CSV erneut geprüft. | Die Prüfung beginnt deutlich weiter oben. Status und Hauptaktion sind erkennbar, ohne zuerst Formulareinstellungen zu lesen. Auf schmalen Displays werden die Spalten untereinander gezeigt. |
| P1 · Upload und Administration aus der Prüffläche nehmen | Import, Modelleinstellungen und Vorgangsdetails öffnen sich bei Bedarf. Der Admin-Schalter ist rollenabhängig. | Edge öffnet und schließt die Bereiche. Import- und Einstellungsansicht separat visuell betrachtet. | Die geschlossene Prüfung zeigt weder Upload-Eingaben noch Modellfelder. |
| P1 · Bildübersicht mit Status und Prüfgrund | Horizontale Bildkarten mit geschützten Vorschaubildern, Status, Prüfgrund und Auswahlmarkierung. | Edge mit drei Demo-Bögen. API-Test für Vorschaubild und Sitzungsgrenzen. Der frühere Ordnerimport wurde mit zehn Dateien geprüft. | Karten lassen mehr Höhe für die Prüfung frei. Auf schmalen Displays scrollt die Bildleiste horizontal. Die Ansicht mit 50 Bildern wurde nicht geprüft. |
| P1 · Bildstelle und Feld verbinden | Feldklick markiert die Originalstelle und das zugehörige Ergebnisfeld. Demo-Bereiche sind fest zugeordnet. Bei Live-Upload werden verfügbare Modellbereiche als Schätzung beschriftet. | Edge für Frage 3 und Freitext, einschließlich Zoom. Markierten Bereich im Vorher/Nachher und mobil betrachtet. | Die Zuordnung ist im Demobogen direkt nachvollziehbar. Bei zwei der drei Live-Bögen fehlten Modellkoordinaten. |
| P2 · Qualität gegen Sollwerte sichtbar machen | Der Bereich „Qualitätsnachweis“ zeigt die gemessene Gemma-Stichprobe mit Feldtreffern, Nenner und falsch grünen Bögen. | Edge klappt den Bereich auf. Die Anzeige wurde visuell betrachtet und mit den drei dokumentierten Modellantworten abgeglichen. | Die Stichprobe ist sichtbar, ohne den Arbeitsablauf zu überladen. Handschrift und schwierige Fotos bleiben offen. |
| Grün und Sammelübernahme | Sammelübernahme bleibt erhalten. Direkt bei den Statuskennzahlen steht, dass Grün technische Regeln bestätigt und die Werte am Original abzugleichen sind. | In Edge betrachtet. API-Tests prüfen die Sammelübernahme und den Ausschluss ungeprüfter Fälle. Der Live-Vergleich ergab 0 von 2 falsch grünen Bögen. | Der Hinweis steht im Kontext der Aktion. Zwei grüne Beispiele erlauben noch keine belastbare Zuverlässigkeitsbewertung. |

## UX-Nachprüfung und zweite Gemma-Stichprobe

Die überarbeitete Pilotoberfläche läuft unter http://127.0.0.1:8003. Der Import öffnet sich als eigener Schritt. Modelleinstellungen sind eingeklappt und nur für die Adminrolle sichtbar. Die Bildliste zeigt geschützte Vorschaubilder, Status und Prüfgrund. Die drei Prüfspalten stehen auf breiten Displays nebeneinander und auf schmalen Displays untereinander.

- Bild 2 nennt Frage 4 als Prüfgrund. Bild 3 trennt den künstlichen Freitext-Prüffall ausdrücklich von einem tatsächlichen Modellbefund und erklärt, warum die vorgegebenen Werte stimmen.
- Echte Antworten können strukturierte Befunde mit Feld, Typ und Begründung liefern. Bei älteren oder knappen Antworten werden konkrete Befunde aus den Feldstatus ergänzt. Akzeptierte Rohantworten bleiben unverändert. Bildbereiche für echte Uploads sind als Schätzungen gekennzeichnet. Ohne brauchbare Koordinaten zeigt die Anwendung einen Hinweis und lässt das Original zur manuellen Kontrolle sichtbar.
- Die Sammelübernahme bleibt verfügbar. Der Hinweis direkt neben den Aktionen erläutert die technischen Kriterien und fordert zum Abgleich mit dem Original auf.
- **28 automatisierte Tests** bestanden. Der Edge-Test bestand bei 1200 und 480 Pixeln Breite. Geprüft wurden Vorschauen, die Prüfgründe von Bild 2 und 3, markierte Bildstellen im Original und im Zoom, Tastaturbedienung des Zooms, manuelle Bestätigung mit CSV-Download sowie die Rollen- und Menüführung.

Für den Qualitätstest wurden die drei synthetischen Druckbilder als reguläre JPEGs hochgeladen und mit `google/gemma-4-26b-a4b-it` live erkannt. Die Ergebnisse stammen aus den Modellaufrufen.

| Bogen | Feldtreffer (Wert und Status) | Freitext gegenüber Soll | Status | Laufzeit |
| --- | --- | --- | --- | --- |
| 01 | 5/5 | Original und Übersetzung stimmen | Grün | 3,77 s |
| 02 | 5/5, einschließlich leerer Antwort und Mehrfachkreuz | Korrekt als leer erkannt | Gelb | 1,92 s |
| 03 | 5/5 | Deutscher Originaltext stimmt | Grün | 2,31 s |

**15/15 Feldtreffer. 0 von 2 grünen Bögen waren in dieser Stichprobe falsch grün.** Das Modell benannte bei Bogen 02 die beiden angekreuzten Optionen korrekt. Es nannte das leere Freitextfeld zusätzlich als Hinweis, obwohl ein leerer Kommentar zulässig ist. Verwertbare Bildkoordinaten lieferte es nur für fünf Fragen in Bogen 03. Die Daten reichen für eine erste Funktionsprobe. Handschrift, schwierige Fotos und eine belastbare Quote falsch grüner Ergebnisse bleiben offen. Die Anwendung weist die Stichprobe als begrenzten Qualitätsnachweis mit den jeweiligen Nennern aus.

## Erste Live-Nachprüfung mit Gemma 4

**Ergebnis des ersten Tests:** Der lokale MVP lief mit dem vorhandenen OpenRouter-Schlüssel unter http://127.0.0.1:8002. In der lokalen `.env` wurde der Modus von `mock` auf `openrouter` umgestellt. Die Modell-ID `google/gemma-4-26b-a4b-it` blieb erhalten. Die Oberfläche bezeichnet den Anbieter jetzt als OpenRouter, passend zum tatsächlich konfigurierten Modell.

- Ein echter multimodaler Aufruf über die Anwendung mit einem synthetischen JPEG und bekannten Sollwerten. Die Erkennungsroute antwortete mit HTTP 200 nach **3,48 Sekunden** und meldete den Datensatz als übernahmebereit.
- **5 von 5 Werten und Feldstatus korrekt.** Q1 bis Q5 lauteten `4, 3, 4, 2, 3`, jeweils `answered`. Das englische Original „Everything was well organized.“ und die deutsche Übersetzung „Alles war gut organisiert.“ entsprachen dem Soll. Die Modellantwort enthielt keine Warnungen.
- Vor der Bestätigung wurde der CSV-Export abgewiesen. Nach manueller Prüfung wurde der Datensatz unverändert bestätigt. Die Rohantwort blieb identisch, und die CSV enthielt genau einen bestätigten Datensatz ohne Originaltranskript.
- Stichprobe mit einem synthetischen Druckbild. Die Erkennungsqualität bei Handschrift, schwierigen Aufnahmen und mehrdeutigen Markierungen muss separat gemessen werden. Der Betrag des einzelnen Aufrufs wurde in der Anwendung nicht erhoben. [OpenRouter-Modellseite](https://openrouter.ai/google/gemma-4-26b-a4b-it)

**Lokaler Startbefehl im Projektordner**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

## Implementiert

Der MVP verarbeitet JPEG und PNG in einem Prozess und verwaltet Vorgänge, Bilder, Modellvorschläge und bestätigte Datensätze in getrennten Arbeitssitzungen. Die Fachfunktionen stehen beiden Rollen zur Verfügung. Die Modellkonfiguration ist Administratoren vorbehalten. Nur bestätigte Datensätze gelangen mit stabilen Vorgangs- und Bild-IDs in die CSV. Grün steht für bestandene technische Regeln. Die drei Demofälle enthalten fest vorgegebene Erkennungsdaten, und der Mock kennzeichnet eigene Uploads zur manuellen Prüfung.

### Behobene Befunde

| Schwere | Befund und Auswirkung | Korrektur |
| --- | --- | --- |
| Hoch | Parallele Erkennungsanfragen konnten für dasselbe Bild Kosten auslösen und spätere Prüfung oder Rohdaten überschreiben. | Serverseitiger Verarbeitungsstatus und Wiederholungen nur für ausstehende bzw. fehlgeschlagene Bilder. Simulierte Modellfehler zählen zum Aufruflimit. |
| Hoch | Der Multipart-Parser las Uploads vor der Authentifizierung. Dateigrößen wurden erst nach dem Einlesen begrenzt. | Authentifizierung und CSRF-Prüfung vor Multipart-Verarbeitung. Begrenzung von Dateizahl, Einzelgröße und Gesamtrequest. Erneute Prüfung des Sitzungskontingents vor dem Speichern. |
| Mittel | Eine fehlerhafte Datei verwarf auch gültige Dateien im selben Upload. | Bei gemischten Uploads bleiben gültige Dateien erhalten. Defekte Dateien werden mit lokalem Fehlerstatus angezeigt. |
| Mittel | Manuelle Änderungen konnten beim Wechsel des Bildes verloren gehen. Die Sammelübernahme konnte grüne Bilder trotz laufender manueller Prüfung finalisieren. | Entwürfe bleiben bei der Navigation im geöffneten Tab erhalten. Sammelübernahme überspringt laufende manuelle Prüfungen. |
| Mittel | CSS konnte `hidden` an Admin- und Belegelementen überstimmen. Erkennungsaktionen konnten nach dem erneuten Rendern deaktiviert bleiben. | Ausblendung ausdrücklich durchgesetzt. Erkennungsaktionen und Ansichtswechsel berücksichtigen den laufenden Request und die ausgewählten IDs. |
| Mittel | Mehrdeutiges oder abgeschnittenes Modell-JSON konnte akzeptiert werden. Lange Rohantworten wurden für die Anzeige gekürzt. | Doppelte JSON-Schlüssel, vorzeitiges Ende und überlange Modelltexte werden abgelehnt. Akzeptierter Antworttext bleibt unverändert. Der Request fordert maximal 4096 Ausgabetokens an. |
| Mittel | Zusätzliche Kontrollzeichen und Formelsymbole konnten den CSV-Formelschutz umgehen. | Gefährliche Zellpräfixe werden beim Export maskiert. Interne Werte bleiben erhalten. |
| Niedrig | Nicht-ASCII im CSRF-Header konnte einen Serverfehler auslösen. Das Loginformular hätte ohne JavaScript Daten per URL gesendet. | CSRF-Vergleich auf Bytebasis, Loginformular auf POST, öffentliche OpenAPI-Route deaktiviert. Beim erneuten Login im selben Browser wird die ersetzte Sitzung serverseitig beendet. |
| Niedrig | Transparenz in PNG konnte beim JPEG-Export dunkel werden. | Transparente Bereiche werden auf Weiß gelegt. Die Bildnormalisierung verwirft Metadaten, nachdem die EXIF-Ausrichtung angewendet wurde. |

## Automatisiert getestet

- Windows, Python 3.12.10 in `.venv`, Node.js 22.16.0. Installation aus `requirements-dev.txt`.
- **27 Tests bestanden** mit `python -m pytest -q`. Eine Deprecation-Warnung betrifft Starlettes Verwendung von HTTPX im Testclient.
- `python -m compileall -q app scripts`, `node --check app/static/app.js`, `python -m pip check` und `git diff --check` erfolgreich.
- API- und Vertragstests prüfen Rollen, CSRF, Sitzungsisolation, Ablauf und Neustart, Upload und EXIF-Rotation, feste Demofälle, parallele Erkennung, Bestätigung und Wiederöffnung sowie CSV-Auswahl und Formelschutz.
- In der automatisierten Testsuite ist OpenRouter simuliert. Geprüft sind Modell-ID, JSON-Modus, Base64-Bild und Requestaufbau, Timeout, ungültige und überlange Antworten, Schemaabweichung und Aufrufgrenzen. Der Prozess akzeptierte im Test insgesamt 80 simulierte Aufrufe und pro Anmeldung höchstens 25. Fehlversuche verbrauchen ebenfalls Kontingent.

## Lokal verifiziert

- Uvicorn an `127.0.0.1:8000` mit `GET /health` → HTTP 200 und `{"status":"ok"}`. Ein kombinierter Neustartbefehl für diesen Prozess wurde durch die lokale Ausführungsrichtlinie blockiert. Der abschließende Browserlauf mit dem neuesten Backend lief deshalb zusätzlich auf `127.0.0.1:8001` und bestand dort ebenfalls. Die Ungültigkeit alter Sitzungen nach Neustart ist automatisiert geprüft.
- Microsoft Edge mit Playwright, normaler und schmaler Ansicht. Admin- und Testlogin, zwei parallele isolierte Testanmeldungen, Demobilder, Bild ein-/ausblenden und vergrößern, leere und mehrfache Markierungen, Originaltranskript und Übersetzung, grüner Sammellauf, Wiederöffnung, erhaltener Tab-Entwurf, Belegprüfung bei Zahlenänderung, Umbenennung, CSV-Download und Exportinhalt, Einzelimport JPEG/PNG, zehn Dateien per Ordnerwahl, Mock-Verarbeitung und Logout bestanden.
- `.env`, virtuelle Umgebung und lokale Zugangsdaten sind von Git ausgeschlossen. Die einmalig erzeugten Passwörter liegen in `local-data/login.txt` mit Zugriff für das aktuelle Windows-Konto. Git-Push und Render-Deployment wurden nicht ausgeführt. Der externe Modellaufruf ist in der Live-Nachprüfung dokumentiert.

## Noch offen

- **Pilotfreigabe:** Echte Bild- und Handschriftqualität einschließlich Übersetzung und falsch grüner Ergebnisse ist offen. Festdaten und HTTP-Simulation prüfen den Workflow und die Schnittstelle. Zehn erzeugte Browser-Importdateien dienten nur dem Importtest. Für den Qualitätstest sind zehn verschiedene handschriftlich ausgefüllte und fotografierte Bögen mit getrennten Sollwerten erforderlich.
- **Öffentlicher Betrieb:** Render-Konfiguration nur statisch anhand der [Blueprint-Referenz](https://render.com/docs/blueprint-spec) geprüft. HTTP-Proxy, HTTPS-Cookies, Online-Neustart und Verhalten unter Last sind offen. Der Dienst arbeitet mit einem Worker, kurzfristigen In-Memory-Sitzungen und IP-basiertem Login-Limit. Das fehlende globale Sitzungs- und Ressourcenlimit ist ein hohes Risiko für einen öffentlichen Betrieb. Last- und Proxytests stehen ebenfalls aus.
- **MVP-Grenzen:** Originalansicht zeigt das normalisierte Bild mit maximal 1800 Pixeln je Seite. Die Übersicht verwendet Dateinamen und Status, die Bildvorschau erscheint im ausgewählten Detail. Unbestätigte Tab-Entwürfe gehen bei Seitenneuladen verloren. Serverdaten gehen bei Logout, Ablauf oder Neustart verloren. Ein Prüfer bestätigt sichtbare Belege selbst. Die Software kann die tatsächliche Übereinstimmung mit dem Bild nicht erzwingen.
- **Sicherheitsprüfung:** Lokaler Code- und Funktionstest einschließlich Rollen, CSRF, Cookie- und Cache-Einstellungen, DOM-Textausgabe, Bildgrenzen und CSV-Formelschutz. Eine unabhängige Sicherheits-, Datenschutz- und Lastfreigabe für reale Daten steht aus.

### Erweiterte Qualitätsprüfung mit OpenRouter

1. Einen separaten OpenRouter-Schlüssel mit kleinem Ausgabenlimit anlegen. Ein aktuell verfügbares Modell auswählen, dessen Endpunkt Bilddaten per Base64 und JSON-Ausgabe unterstützt. [Vision-Modelle](https://openrouter.ai/collections/vision-models/) · [Schlüssel- und Ausgabenlimits](https://openrouter.ai/docs/api/reference/limits)
2. Lokal in `.env` `MODEL_PROVIDER=openrouter`, `OPENROUTER_API_KEY` und `OPENROUTER_MODEL` setzen. Server neu starten. Der Adminbereich zeigt, ob ein Schlüssel hinterlegt ist.
3. Einen eigenen synthetischen Bogen hochladen und zunächst nur dieses Bild erkennen lassen. Prüfen, ob Original, unveränderte Modellantwort, fünf Feldstatus, Originaltranskript, Übersetzung und bestätigter Export plausibel zusammenpassen. Anbieteraufruf und Kosten prüfen.
4. Die zehn Fälle aus [TEST_PLAN.md](TEST_PLAN.md) gegen vorher dokumentierte Sollwerte prüfen. Feldtreffer, falsch grüne Fälle, Transkriptions- und Übersetzungsfehler sowie Fehlerquote, Laufzeit und Kosten erfassen. Erst danach die Pilotfreigabe entscheiden. Anschließend bei Bedarf wieder `MODEL_PROVIDER=mock` setzen und den Server neu starten.
