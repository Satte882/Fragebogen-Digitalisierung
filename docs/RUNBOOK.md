# Betrieb und Online-Demo – Form Digitizer

**MVP, keine produktive Installation.** Nur eigene/synthetische Testdaten.

## Windows

~~~powershell
git clone https://github.com/Satte882/Fragebogen-Digitalisierung.git
cd Fragebogen-Digitalisierung
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python scripts/bootstrap_local.py
python -m uvicorn app.main:app --reload
~~~

`bootstrap_local.py` legt eine private `.env` an und zeigt die Passwörter für **admin** und **test** einmalig. `.env` bleibt lokal und darf nie veröffentlicht werden. Auf http://127.0.0.1:8000 anmelden, **Synthetische Demo laden** und den Ablauf ohne API-Kosten ausprobieren. Eigene Bild-Uploads im Demo-Modus werden ausdrücklich **nicht** automatisch erkannt.

## OpenRouter

In `.env` eintragen und Server neu starten:

~~~dotenv
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=google/gemini-2.5-flash
~~~

Die Modell-ID ist ein **Beispiel**; aktuell verfügbares bildfähiges Modell unter https://openrouter.ai/models prüfen. Bei diesem Modus werden die Bilder an OpenRouter beziehungsweise Modellanbieter übermittelt. Die korrekte Transkription ist erst nach realer Gegenprüfung mit bekannten Testfotos nachgewiesen. Admin kann Modell/Modus bis zum nächsten Neustart in der UI wechseln; Testnutzer können alle Fachfunktionen ausführen, aber keine technischen Einstellungen ändern.

## Render Free bereitstellen

1. **GitHub freigeben.** Den geprüften Veröffentlichungsbranch `codex/render-demo-release` ansehen. Er enthält denselben Anwendungsstand wie `codex/render-readiness`, bereinigt um die lokalen QA-Screenshots. Nach separater Freigabe nur den Veröffentlichungsbranch veröffentlichen. Der öffentliche Branch `main` bleibt unverändert.

   ~~~powershell
   git push -u origin codex/render-demo-release
   ~~~

2. **Zugänge vorbereiten.** Im Passwortmanager zwei unterschiedliche, zufällige Passwörter mit mindestens 24 Zeichen erzeugen. Lokal im Projektordner je Rolle einen Hash erzeugen. Die Eingabe bleibt verborgen. Die Ausgabe ist der Hashwert für Render.

   ~~~powershell
   .\.venv\Scripts\python.exe -c "from getpass import getpass; from app.security import password_hash; print(password_hash(getpass('Admin-Passwort: ')))"
   .\.venv\Scripts\python.exe -c "from getpass import getpass; from app.security import password_hash; print(password_hash(getpass('Test-Passwort: ')))"
   ~~~

3. **Render separat freigeben.** Im Render-Dashboard unter **New → Blueprint** das GitHub-Repository und den Branch `codex/render-demo-release` wählen. [render.yaml](../render.yaml) definiert genau einen kostenlosen Python-Web-Service. Im Plan auf **Free**, den richtigen Branch, den Verzicht auf weitere Ressourcen und ausgeschaltete automatische Bereitstellungen achten. Bei Einrichtung über das Blueprint-Tool auch automatische Blueprint-Synchronisierung deaktivieren. Plan erst nach ausdrücklicher Freigabe anwenden. [Render Blueprint-Referenz](https://render.com/docs/blueprint-spec)
4. **Geheimnisse direkt bei Render eingeben.** Die erzeugten Hashwerte in `ADMIN_PASSWORD_HASH` und `TEST_PASSWORD_HASH` einfügen, ohne Anführungszeichen. `SESSION_SECRET` erzeugt Render automatisch. Klartextpasswörter nur im Passwortmanager und über einen privaten Kanal teilen. Zum Login heißen die Konten `admin` und `test`. Der Testzugang ist gemeinsam, die Arbeitsbereiche sind pro Anmeldung getrennt. Fehlende oder falsch formatierte Anmeldedaten verhindern den Start.
5. **Nach der Bereitstellung prüfen.** Die HTTPS-URL und `/health` öffnen, beide Rollen prüfen, in zwei privaten Browserprofilen getrennt als `test` anmelden. Nur im ersten Profil **Demo-Werkzeuge → Neue Batch-Demo · 30 Bögen** laden. Die zweite Anmeldung darf den Vorgang nicht sehen. CSV exportieren und im Render-Dashboard Speicherverbrauch sowie Neustarts prüfen. Vor der Einladung den Online-Test abschließen.
6. **Betrieb.** Sitzungen und offene Daten liegen im Arbeitsspeicher. Nach Neustart, Deployment oder Einschlafen sind sie verloren. Render Free kann nach 15 Minuten ohne Verkehr einschlafen. CSV vor Unterbrechungen herunterladen. Eingeladene Personen verwenden ausschließlich eigene synthetische Daten. Free-Stunden, Bandbreite und Build-Minuten sind getrennte Kontingente. Die Abrechnungseinstellungen des Arbeitsbereichs vor der Freigabe prüfen. [Render Free](https://render.com/docs/free)

### Variablen für das Free-Profil

| Variablen | Wert und Zweck |
| --- | --- |
| `ADMIN_PASSWORD_HASH`, `TEST_PASSWORD_HASH` | Erforderlich. Jeweils den separat erzeugten scrypt-Hash im Dashboard eingeben. |
| `SESSION_SECRET` | Erforderlich. Blueprint erzeugt einen zufälligen Wert. Bei manueller Einrichtung einen eigenen zufälligen Wert mit mindestens 32 Zeichen setzen. |
| `PYTHON_VERSION`, `APP_ENV`, `PORT` | `3.12.10`, `production`, Port von Render. Der Server bindet an `0.0.0.0`, mit einem Worker und höchstens 24 gleichzeitigen Verbindungen bzw. Tasks. `/health` bleibt öffentlich und liefert nur den Gesundheitsstatus. |
| `MODEL_PROVIDER`, `ALLOW_LIVE_MODEL` | `openrouter`, `true` für echte Erkennung. Für einen Betrieb ohne Modellzugang `mock`, `false` setzen. |
| `MAX_IMAGES_PER_SESSION`, `MAX_SESSIONS` | `40` Bilder je Sitzung, `4` aktive Sitzungen pro Prozess einschließlich Admin. |
| `MAX_UPLOAD_MB`, `MAX_BATCH_UPLOAD_MB`, `MAX_WORKSPACE_MB` | `5` MiB pro Datei, `120` MiB pro Upload plus Formular-Overhead, `48` MiB gespeicherte Bilder und Vorschauen pro Sitzung. Maximal ein Upload gleichzeitig. |
| `IMAGE_MAX_EDGE`, `IMAGE_JPEG_QUALITY` | `1800` Pixel, `86`. Eingaben bis 20 Megapixel. |
| `SESSION_TTL_MINUTES` | `120`. Der Timer verlängert sich nicht automatisch. |
| `BATCH_PARALLELISM`, `PROVIDER_RETRIES` | `1` paralleler Modellaufruf, `0` automatische Wiederholungen. |
| `LIVE_CALLS_PER_SESSION`, `LIVE_CALLS_GLOBAL` | `40` Modellaufrufe pro Sitzung und `60` pro Prozess, einschließlich Wiederholungen und Fehlern. |

### Spätere Freigabe von OpenRouter

Für Live-Erkennung `OPENROUTER_API_KEY` im Render-Dashboard als Geheimnis setzen. Der Blueprint setzt `OPENROUTER_MODEL=google/gemma-4-26b-a4b-it`, `MODEL_PROVIDER=openrouter` und `ALLOW_LIVE_MODEL=true`. Vorbereitete Demo-Bögen bleiben verfügbar und verbrauchen kein Modellbudget. Der Free-Dienst verwendet einen parallelen Aufruf, null automatische Wiederholungen, höchstens 40 Aufrufe je Sitzung und 60 je Prozess. Ein Ausgabenlimit am OpenRouter-Schlüssel gilt auch nach Render-Neustarts.

Für diese Demo einen separaten OpenRouter-Key mit einem kleinen Anbieterbudget einsetzen. Die Anwendungslimits zählen Aufrufe. Sie messen keine Kosten und werden bei Prozessneustart zurückgesetzt. Vor Einladungen einen einzelnen eigenen synthetischen Bogen prüfen und im Anbieter-Dashboard Modell, Abrechnung und Limits kontrollieren. [OpenRouter-Limits](https://openrouter.ai/docs/api/reference/limits)

## Grenzen / Schutzmechanismen

- Gemeinsamer Testlogin, aber **separate Sessions pro Anmeldung**. Beim Logout/Timeout/Serverneustart werden Sitzungsdaten gelöscht.
- CSRF-Schutz, HttpOnly/SameSite-Cookie, in `production` nur HTTPS-Cookie, Rollenprüfung auf dem Server.
- JPEG/PNG werden normalisiert und ohne EXIF gespeichert. Für die Online-Demo gelten die engeren Grenzen aus der Tabelle.
- Pro Minute werden pro IP höchstens acht fehlgeschlagene Anmeldeversuche und pro Prozess höchstens 40 Anmeldeversuche zugelassen. Hinter dem Proxy kann das IP-Limit mehrere Personen gemeinsam treffen. Zusätzlich greifen die Sitzungslimits.
- Keine dauerhafte Datenbank, kein produktiver Datenschutz-/Sicherheitsnachweis.

## Testen

~~~powershell
python -m pytest -q
python -m compileall -q app scripts
~~~

Die automatisierten Tests verwenden Mock/HTTP-Simulation und benötigen **keine** echten API-Schlüssel. Die Ergebnisse der lokalen Browserprüfung stehen im [Abnahmebericht](LOCAL_VERIFICATION.md). Die Erkennung mit einem tatsächlichen Gemini-Modell und synthetischen Handschriftfotos ist gesondert zu prüfen.
