# Technische Architektur – implementierter MVP

**Pilotcode, kein Produktivsystem.** Code und API-Tests vorhanden; Live-Modellgüte und Online-Deployment noch nicht verifiziert.

## Komponenten

- `app/main.py`: FastAPI-Routen, Upload-/Bilderprüfung, Vorgänge, Workflow, Sessions, Autorisierung.
- `app/security.py`: Scrypt-Passworthashes, begrenzte Login-Versuche, isolierte kurzlebige Sessions.
- `app/config.py`: Umgebungsvariablen; Serverstart ohne Geheimnisse **verweigert**.
- `app/contracts.py`: Strenge Feldstatus (answered/no_answer/multiple/unreadable), Wert 1–4 oder null, Freitext, finale Übernahme.
- `app/providers.py`: `ImageProvider`-Adapter; OpenRouter mit Base64-JPEG und JSON-Antwort oder Mock ohne KI-Erkennung.
- `app/demo.py`: Drei sichtbare **synthetische** Fixfälle (keine KI-Erkennung).
- `app/export.py`: CSV aus final bestätigten Daten, ohne KI-Rohdaten, Excel-Formelschutz.
- `app/static/`: Vanilla-JS/HTML/CSS für Ordnerimport und Dreispalten-Prüfung.
- `tests/`: Funktionale Tests inklusive OpenRouter-HTTP-Simulation.

## Ablauf

Login → je Anmeldung isolierter Arbeitsspeicher → Ordner/JPEG/PNG → normalisierte EXIF-freie JPEGs → Model-Adapter → streng validierter Zwischen-Datensatz → grün/gelb/Fehler → Bild/Roh-Erkennung/finaler Datensatz → visuelle Prüfung/Bestätigung → CSV nur mit Finalwerten.

**Grün ≠ 100 % korrekt.** Die KI-Roh-Erkennung ist als eigener Zustand sichtbar, aber nie Teil der CSV. Fehlende Kreuze bleiben ohne Wert. Eine erkannte leere/unlesbare Frage darf nicht ohne bestätigten visuellen Beleg mit einem Zahlenwert gefüllt werden. Übersetzung ist keine Textglättung oder Analyse.

## Zugang und Sicherheit

Admin und gemeinsamer Testlogin haben **gleiche fachliche Funktionen**; nur Admin verwaltet den Modelladapter. Verschiedene Anmeldungen des Testkontos teilen keine Uploads oder Exporte. Schreibende Routen benötigen CSRF-Token; alle Vorgangs-/Bild-IDs sind serverseitig auf die Sitzung beschränkt. Cookies HttpOnly/SameSite, in Produktion Secure; Bildbegrenzung, Dateinormalisierung, EXIF-Entfernung, generische API-Fehler. OpenRouter-Key nur serverseitig. Live-Aufrufe standardmäßig max. 100 pro Sitzung/250 insgesamt pro Prozess. Zusätzlich echtes API-Budgetlimit setzen.

Ein einzelner Worker ist Voraussetzung, weil die Sessions im Arbeitsspeicher liegen. Bei Neustart, Logout oder Timeout gehen Arbeitsdaten verloren. Keine Datenbank. Für Render Free ist das vertretbar als zeitlich begrenzte **Demo**, nicht als dauerhaftes System.

## Verarbeitungsläufe

Ein Lauf belegt seine Bilder serverseitig und ist pro Vorgang idempotent, solange er läuft. In-Process-Worker teilen sich ein prozessweites Parallelitätslimit. Browser-Polling liest die Status im isolierten Arbeitsbereich. Der Anbieter wird beim Start pro Lauf festgelegt. Nur Timeout, Rate Limit und vorübergehende Anbieterfehler werden automatisch wiederholt. Die Wiederholungen respektieren begrenzten Backoff und einen kurzen Retry-After. Bei längerer Anbieterwartezeit bleibt der Fehler für den manuellen Neustart sichtbar. Jeder gesendete Aufruf belastet Sitzung und Prozess. Die Laufmetadaten enthalten Modell, Prompt-Version, UTC-Start, Dauer, Ergebnis und Anzahl der Aufrufe.

## Modellwechsel

Gemini über OpenRouter verwendet `POST /api/v1/chat/completions` mit Bilddaten im Base64-`image_url` und `response_format=json_object`. Ein anderer Endpunkt kann mit einem neuen Adapter an dieselbe `Recognition`-Schnittstelle angeschlossen werden. Ein Wechsel erfordert immer eine neue **Qualitätsmessung**.
