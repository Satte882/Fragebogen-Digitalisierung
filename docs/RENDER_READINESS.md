# Render-Readiness · Form Digitizer

**Entscheidung: GO WITH LIMITATIONS für eine geschützte synthetische Demo auf Render Free.** Freigabe für Live-Erkennung mit OpenRouter erst nach separater Genehmigung, Einrichtung eines Anbieterbudgets und erfolgreicher Online-Abnahme.

**Prüfbasis:** Lokaler Commit `3fea040` mit allen bisherigen Workflow- und Korrekturverbesserungen. GitHub `main` stand bei der Prüfung auf `473695d`. Der geprüfte lokale Entwicklungsstand bleibt auf `codex/render-readiness`. Der vorbereitete Branch `codex/render-demo-release` enthält denselben Anwendungsstand und den aktuellen Blueprint. Er basiert als Veröffentlichungssnapshot auf dem bereits öffentlichen `origin/main` und enthält weder die lokalen Screenshots noch deren Historie. GitHub- und Render-Freigabe sind getrennte Schritte.

## Test unter Render-ähnlichen Grenzen

- Linux unter WSL, echte TLS-Verbindung auf Loopback mit temporärem lokalem Zertifikat, `APP_ENV=production`, ein Uvicorn-Worker. Für die vollständige Windows-Suite wurde die im Blueprint festgelegte Python-Version 3.12.10 verwendet. WSL nutzt Python 3.12.3.
- Der Linux-Cgroup-Kernel meldete ein CPU-Kontingent von 10.000 µs je 100.000 µs und ein Speicherlimit von 536.870.912 Byte. Der Lastgenerator lief außerhalb des Server-Cgroups. Der Test misst einen lokalen Linux-Prozess. Render-Proxy, Kaltstart und laufender Cloud-Betrieb werden erst nach Freigabe geprüft.
- Zwei gleichzeitig angemeldete `test`-Clients sowie eine Adminsitzung. Im ersten Arbeitsbereich 30 vorbereitete Demo-Bögen mit 26 Sammelübernahmen, vier Einzelprüfungen und 30 CSV-Zeilen. Der zweite Arbeitsbereich lud 30 synthetische 4000×3000-JPEGs hoch und verarbeitete sie im Mock. Dabei blieb der erste Vorgang im Speicher.
- Die 30 Upload-Dateien hatten je 4.134.165 Byte und zusammen 118,28 MiB. Der Upload einschließlich Normalisierung dauerte 111,01 Sekunden. Die Spitze im gesamten Server-Cgroup lag bei **321,37 MiB** einschließlich Kernel-Speicherabrechnung und Dateicache. Der Serverprozess erreichte **210,10 MiB** Spitzen-RSS. Im Cgroup blieben rechnerisch 190,63 MiB bis zum harten Limit. Die lange Upload-Zeit muss nach Freigabe am Render-Proxy verifiziert werden.
- TLS bestätigte `Secure`, `HttpOnly` und `SameSite=Lax`. Der Client sendete das Sitzungscookie bei HTTP nicht mit. Die zweite Sitzung konnte Vorgang, Bildvorschau und CSV der ersten nicht abrufen. CSRF wurde serverseitig abgewiesen. Admin- und Testrechte waren getrennt. Live-Aktivierung wurde bei gesetzter Sperre auch für Admin abgewiesen. Ein Start ohne Session-Secret schlug fehl. Nach einem Prozessneustart war das alte Cookie ungültig und der neu angemeldete Arbeitsbereich leer.

## Weitere Prüfungen

| Kriterium | Ergebnis |
| --- | --- |
| Blueprint | Gegen das aktuelle offizielle Render-JSON-Schema validiert. Ein Free-Web-Service, explizit ein Worker, `$PORT`, `/health`, automatische Deploys ausgeschaltet. |
| Automatisierte Tests | 47 Tests bestanden. Abgedeckt sind fehlende oder ungültige Secrets, Cookie-Regeln, CSRF, Zugriffsschutz, Uploadgrenzen und ungültige Dateien, isolierte Sitzungen, Adminrechte, Aufrufgrenzen und Wiederholungen, Rate-Limiting und das Ausblenden von Passwort-Eingaben in Validierungsfehlern. |
| Ressourcenbegrenzung | Vier aktive Sitzungen, 40 Bilder und 48 MiB normalisierte Bilder samt Vorschauen je Sitzung, 5 MiB pro Datei, 120 MiB Upload-Gesamtgröße plus Formular-Overhead, höchstens ein Upload gleichzeitig und 20 Korrekturrevisionen je Bogen. Die 48 MiB sind ein Bildspeicherlimit, kein Limit für den gesamten Prozess. |
| Modellkosten | Start in Mock mit gesperrtem Live-Modell. Später 40 Aufrufe je Sitzung, 80 pro Prozess, ein paralleler Aufruf und höchstens eine automatische Wiederholung. Fehlversuche zählen. Keine echten Modellaufrufe in dieser Abnahme. |
| Git und Datenschutz | Git-Historie, vorgesehene Änderungen und Index wurden anhand verbotener Pfade, bekannter Token- und Schlüsselformate sowie der exakten lokalen Geheimnisse geprüft. Keine Treffer. 23 vorhandene synthetische QA-Screenshots bleiben im lokalen Entwicklungszweig. Der Veröffentlichungsbranch hat keine Foto-, Screenshot-, CSV- oder Secret-Dateien. Die Prüfung ist kein Beweis für die Abwesenheit jedes denkbaren Geheimnisformats. |

## Betriebsgrenzen

- Render Free kann nach 15 Minuten ohne Verkehr schlafen. Der Wiederanlauf kann etwa eine Minute dauern. Neustart, Deployment und Schlafzustand verwerfen alle Sitzungen und nicht exportierten Daten. [Render Free](https://render.com/docs/free)
- Der Lasttest deckt einen 30er-Upload bei gleichzeitig belegtem Demo-Arbeitsbereich ab. Er misst weder den Worst Case mit vier vollen Arbeitsbereichen noch die Randbedingungen des echten Render-Proxys. Die niedrigere Bildkante im Free-Profil reduziert Speicherbedarf. Ihre Auswirkungen auf Handschrift und feine Markierungen wurden hier nicht gemessen.
- Das gemeinsame Testpasswort erlaubt Zugriff für Personen mit dem Passwort. Es gibt keine individuellen Einladungs- oder Widerrufsrechte. Die Arbeitsbereiche sind technisch getrennt. Die IP-basierte Grenze kann hinter dem Proxy oder im selben Netzwerk mehrere Personen betreffen. Die öffentliche Login-Seite bleibt grundsätzlich erreichbar.
- Die Anwendungsgrenzen für OpenRouter gelten je Prozess und starten nach einem Neustart neu. Ein separates Anbieterbudget ist Voraussetzung für eine kostenbegrenzte Live-Demo. Auch Render Free hat Kontingente für Bandbreite und Build-Minuten. Die Abrechnungseinstellungen vor Freigabe prüfen. [OpenRouter-Limits](https://openrouter.ai/docs/api/reference/limits)

**Freigabeschritte:** Zuerst den Commit von `codex/render-demo-release` zur Veröffentlichung auf GitHub freigeben. Danach den Render-Plan mit genau einem kostenlosen Web-Service prüfen und separat zur Anwendung freigeben. Die Anleitung und alle Variablen stehen im [Runbook](RUNBOOK.md). Es wurde weder gepusht noch bereitgestellt oder ein externer Zugang angelegt.
