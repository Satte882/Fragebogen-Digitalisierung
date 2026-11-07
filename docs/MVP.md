# MVP-Spezifikation – Form Digitizer

**Stand:** 07.11.2026 · **Geltung:** Erster funktionsfähiger Pilot, keine Produktivfreigabe

## 1. Ziel und Nicht-Ziel

**Ziel:** Mehrere Fotos eines **festen** Papierfragebogens in eine überprüfbare, strukturierte digitale Form übertragen und die bestätigten Werte als CSV bereitstellen. Die Demo muss mit selbst erstellten, künstlichen Inhalten nachvollziehbar funktionieren.

**Kein Ziel:** Auswertung der Bewertungen, Sentimentanalyse, Zusammenfassungen, automatisierte Entscheidung, Datenbankintegration, echtes Enterprise-Identity-Management, generischer Parser für beliebige Formulare.

## 2. Ausgangsformular

- Genau fünf Bewertungsfragen, je eine Skala mit den Antwortoptionen **1, 2, 3, 4**.
- Jede Frage kann eine eindeutige Markierung, keine Markierung, mehrere Markierungen oder eine nicht sicher lesbare Markierung enthalten.
- Ein Freitextfeld für circa vier bis fünf handschriftliche Zeilen; Schrift kann mehrsprachig sein.
- Ein eigener neutraler Musterbogen liegt unter **examples/musterfragebogen.html**.
- Die 1–4-Skala wird zunächst als **Wert**, nicht als positive/negative Bewertung behandelt.

## 3. Rollen und Zugang

| Funktion | Administrator | Gemeinsamer Testzugang |
| --- | --- | --- |
| Anmelden | Ja | Ja |
| Foto-/Ordnerimport, Vorgang umbenennen | Ja | Ja |
| Erkennung starten, Vorschläge prüfen | Ja | Ja |
| Felder korrigieren, final bestätigen | Ja | Ja |
| CSV herunterladen | Ja | Ja |
| Eigene Arbeitsvorgänge | Ja | Ja |
| Modellkonfiguration und technische Einstellungen | Ja | Nein |

**Wichtig:** Ein gemeinsames Testkonto bedeutet **nicht** einen gemeinsamen Arbeitsbereich. Jeder erfolgreiche Login erzeugt eine eigene zufällige Sitzungs-/Arbeitsbereichskennung; die serverseitigen Vorgangs- und Bildzugriffe werden auf diese Kennung begrenzt. Browser und Sitzungen dürfen fremde Uploads nicht sehen. Demo-Accounts enthalten keine personenbezogenen Daten.

## 4. Screens und Interaktionen

### A. Anmeldung

Einfaches Login mit Administrator- und Testrolle. Keine öffentliche Datenverarbeitungsseite ohne Login. Vorbereitete synthetische Demo kann nach Login gestartet werden. Keine echten Zugangsdaten im Repository oder Frontend. Die Kopfleiste bleibt beim Scrollen sichtbar. Administratoren können die geöffneten Modelleinstellungen über „Schließen“ oder per Escape im Einstellungsbereich verlassen.

### B. Vorgang anlegen / Fotos importieren

- Auswahl **eines lokalen Fotoordners** oder alternativ mehrerer Einzelbilder im Browser; der Ordnername ist ausschließlich ein Vorschlag.
- Unterstützte MVP-Eingaben: **JPEG und PNG**. Andere Formate erst nach Bedarf, keine automatische PDF-Erstellung.
- Fünf versionierte Handschrift-Beispiele werden als offene Bilder in den eigenen Vorgang geladen. Erst die ausdrücklich gestartete Erkennung übermittelt sie ans Modell. Die leere Vorlage ist separat nach Login herunterladbar. Die vorbereitete 30-Bögen-Demo bleibt ohne Modellaufrufe verfügbar.
- Die Demo ist für Desktop-PCs ausgelegt. Maßgeblich für die UI-Abnahme sind 1366 × 768 Pixel und größere Desktop-Fenster. Breite Arbeitsflächen sollen ausgenutzt werden. Handy und Tablet gehören nicht zur UI-Abnahme.
- Vorgangsname ist vor und nach dem Import editierbar (Beispiel: „Veranstaltung Nord – 02.05.2026“). Ein Hinweis erklärt die Übernahme in die CSV. Die Oberfläche bildet die Bogenbezeichnung aus dem aktuellen Vorgangsnamen und der laufenden Nummer (z. B. „Veranstaltung Nord – 02.05.2026 · Bogen 001“). Beim Umbenennen bleiben Vorgangs-ID, Bild-ID, Nummer und ursprünglicher Dateiname erhalten.
- System vergibt eindeutige Vorgangs-ID und je Bild eine stabile Bild-ID; dazu Dateiname und Reihenfolge.
- Standardmäßig sind 40 Bilder pro Sitzung möglich. Die 30-Bögen-Demo verarbeitet 26 grüne und vier gelbe Festfälle ohne Anbieteraufrufe.
- Übersicht zeigt Bildanzahl, Vorschaubilder, Status, Fortschritt und Fehler. Ein einzelner Fehlversuch darf nicht den gesamten Batch zerstören.

### C. Batch-Übersicht

Jedes Bild hat einen Status:
- **Noch nicht verarbeitet / Wird verarbeitet**
- **Übernahmebereit (grün)**: Schema und Prüfregeln erfüllt; keine behauptete absolute Genauigkeit.
- **Prüfung erforderlich (gelb)**: mindestens ein unsicheres Feld, widersprüchliche Markierung oder fragliche Übersetzung.
- **Fehler (rot)**: Bild unbrauchbar, API- oder Parserfehler, erneuter Versuch möglich.
- **Final übernommen**: Mensch hat den Datensatz bestätigt; zusätzlich wird gespeichert, ob korrigiert wurde.

Die Vorgangsübersicht zeigt standardmäßig „Zu prüfen“, wenn Prüffälle vorliegen. Sichtbare Filter mit Anzahl führen zu übernahmebereiten, bestätigten oder allen Bögen sowie zu technischen Fehlern, wenn vorhanden. Die Batch-Demo öffnet sich mit vorbereiteten Ergebnissen sofort. Erst die Auswahl eines Bildes öffnet dessen Detailansicht. Vorgänge können direkt in der Überschrift umbenannt und aus der eigenen Sitzung gelöscht werden. Während laufender Verarbeitung ist das Löschen gesperrt. Ein serverseitiger Lauf verarbeitet den Vorgang und übersteht das Neuladen der Seite innerhalb derselben Sitzung. Ausnahmen lassen sich filtern und nacheinander prüfen. Grüne Ergebnisse können gesammelt übernommen werden. Die Herkunft der Bestätigung wird intern getrennt erfasst.

### D. Dreispaltenansicht – immer dasselbe Prinzip

| Links: Original | Mitte: KI-Erkennung | Rechts: Finaler Datensatz |
| --- | --- | --- |
| Eingereichtes Foto in vergrößerbarer Ansicht; ein-/ausblendbar | Originale, unveränderte Modellantwort **strukturiert dargestellt**; Feldstatus, Originaltranskript und Übersetzung sichtbar | Validierte fünf Werte und deutscher Freitext; hier werden menschliche Korrekturen vorgenommen und endgültig übernommen |

**Übernahmebereiter Fall:** Rechts stehen die Werte bereits als Vorschlag. Aktion „Final übernehmen“ übernimmt diese ohne Änderungen; optional kann der Nutzer auf „Bearbeiten“ wechseln.

**Unklarer Fall:** Problemfelder werden auf Feldebene markiert; der Fall bleibt offen. Beim Öffnen sind die vorgeschlagenen Werte sofort editierbar. „Korrektur speichern & bestätigen“ schließt den Bogen mit einem Klick ab und öffnet den nächsten Prüffall. Die Prüfüberschrift nennt die tatsächliche Bildnummer und die Gesamtzahl. Daneben steht die Zahl der noch offenen Prüffälle einschließlich des angezeigten Bogens. Nach dem Speichern nennt eine kurze Rückmeldung den gespeicherten Bogen und gegebenenfalls den nächsten Bogen. Nach dem letzten Fall erscheint die Vorgangsübersicht mit Sammelbestätigung oder Abschluss und Export. Für Korrekturen ist zusätzlich eine ausdrückliche menschliche Belegbestätigung erforderlich. Unveränderte KI-Ausgabe in der mittleren Spalte bleibt erhalten.

**Wichtige UX-Regel:** Ein eindeutig leeres Kästchen ist kein Fehler. Wenn ein Kreuz erkennbar aber keiner Option sicher zuordenbar ist, bleibt es unklar; die KI oder der Prüfer darf keine Antwort **raten**. Ein Korrekturvorgang darf nur den sichtbaren Formularinhalt getreu übertragen.

**Sichtbarkeit:** Die mittlere Spalte muss die ursprüngliche Handschrift-Transkription und die deutsche Übersetzung unterscheiden. Das Originalbild bleibt jederzeit zur Gegenprüfung erreichbar. Eine vermeintliche Modell-Konfidenz ist kein Korrektheitsbeweis.

### E. Abschluss und Export

- Statusanzeige, z. B. „10 Fotos: 8 ohne Korrektur final übernommen, 2 manuell korrigiert, 0 offen“.
- Die Sammelbestätigung steht direkt unter der Prüfliste. Der CSV-Download ist der letzte Arbeitsschritt. **„CSV herunterladen“** exportiert **nur final bestätigte Datensätze**. Offene Bilder werden nicht stillschweigend mitexportiert; die Zahl der ausgelassenen Bilder wird klar angegeben.
- Eine Zeile entspricht einem Foto/Formular; Vorgangs-ID, Name, Bild-ID, Dateiname, Q1–Q5, Feldstatus, deutscher Freitext und Prüfstatus sind enthalten.
- Keine doppelte KI-Roh-Erkennung im CSV. Keine zwingende Datenbank.

## 5. Fachliche Regeln

1. Pro Frage maximal eine gültige Auswahl aus 1–4.
2. Leeres Feld = Status **keine_antwort**, Wert leer; nicht automatisch vom Menschen nachtragen.
3. Erkennbar widersprüchliche Mehrfachmarkierungen = **mehrfach** und kein numerischer Wert; keine Auswahl ohne evidenten Quellbeleg.
4. Nicht lesbare Markierung = **unklar**; Prüfer darf sichtbare Informationen präzisieren, ansonsten bleibt Wert leer mit entsprechendem Status.
5. Freitext: Original in ursprünglicher Sprache möglichst wortgetreu transkribieren, zusätzlich möglichst sinngetreu ins **Deutsche** übersetzen; **keine inhaltliche Glättung oder Ergänzung**.
6. Unleserliche Stellen als solche markieren, nicht halluzinieren. Bei fehlendem Kommentar Status **leer**, ohne generierten Ersatztext.
7. Alle finalen Antworten müssen nach Prüfung technisch valide sein; auch „keine Antwort“ und „mehrfach“ sind zulässige finale **Statuswerte**, keine erfundenen Antworten.
8. Bei jedem Bild Fehler und Unklarheiten lokal zur betroffenen Frage bzw. Freitextstelle anzeigen.

## 6. MVP-Abnahme

- [ ] Fünf Fragen und Freitext sind auf dem neutralen Musterbogen enthalten.
- [ ] Ordnerimport mit 30 Fotos funktioniert; Vorgangsname bleibt editierbar und Bilder bleiben zugeordnet.
- [ ] Alle Fotos erscheinen mit eindeutiger Bild-ID und korrekt getrenntem Status.
- [ ] KI liefert strukturierte Werte, Originaltranskript und deutsche Übersetzung oder markiert Unsicherheit.
- [ ] Rechtes Prüffeld wird bei grünen Fällen vorausgefüllt; gelbe Fälle sind direkt editierbar und müssen ausdrücklich final bestätigt werden.
- [ ] Bei fehlenden Kreuzen wird **keine_antwort** und niemals ein erfundener Skalenwert ausgegeben.
- [ ] Originalbild, ursprüngliche KI-Erkennung und finale Bestätigung bleiben im Arbeitsbereich vergleichbar.
- [ ] Zwei verschiedene Testanmeldungen mit demselben Testlogin sehen keine gegenseitigen Arbeitsdaten.
- [ ] Test- und Adminkonto können alle Fachfunktionen einschließlich CSV nutzen; nur Admin ändert technische Einstellungen.
- [ ] CSV enthält ausschließlich bestätigte Ergebnisse plus Metadaten, keine doppelten KI-Rohdaten.
- [ ] Fehler, Neustart und Sitzungsende führen nicht zu einer irreführenden „gespeichert“-Anzeige.
- [ ] Keine Unternehmensdaten, Geheimnisse oder personenbezogenen Echtinformationen im öffentlichen Repository.

## 7. Offene Implementierungsdetails (keine offenen Grundsatzentscheidungen)

Konkrete Modell-ID, Upload- und Rate-Limits, Sitzungsdauer und UI-Bibliothek werden bei Implementierung konfigurierbar festgelegt. Keine dieser Entscheidungen ändert den beschriebenen Fachprozess.
