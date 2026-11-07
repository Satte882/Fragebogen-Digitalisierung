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

## Render

[render.yaml](../render.yaml) kann als Render Blueprint importiert werden. Erforderliche Geheimnisse im Dashboard (niemals im Git-Repo): `ADMIN_PASSWORD_HASH`, `TEST_PASSWORD_HASH`. Die Hashwerte stammen aus lokalem `.env`; die Klartextpasswörter bleiben privat. `SESSION_SECRET` wird vom Blueprint erzeugt. Falls echte KI-Aufrufe gewünscht sind, zusätzlich `OPENROUTER_API_KEY`, `MODEL_PROVIDER=openrouter`, `OPENROUTER_MODEL=<aktuelle Gemini-ID>` setzen. Fehlende Anmeldesecrets verhindern **absichtlich** den Serverstart.

Render Free kann nach Inaktivität schlafen und verliert bei Neustart den In-Memory-Inhalt. **Nur ein Worker**: Der Arbeitsbereich ist nicht für Lastverteiler/mehrere Worker ausgelegt. Sitzungen enden nach 60 Minuten; nicht exportierte Daten gehen verloren. Nicht für sensible Daten oder langfristige Speicherung geeignet. https://render.com/docs/free

## Grenzen / Schutzmechanismen

- Gemeinsamer Testlogin, aber **separate Sessions pro Anmeldung**. Beim Logout/Timeout/Serverneustart werden Sitzungsdaten gelöscht.
- CSRF-Schutz, HttpOnly/SameSite-Cookie, in `production` nur HTTPS-Cookie, Rollenprüfung auf dem Server.
- Maximal 20 Bilder pro Sitzung, maximal 10 MB pro Datei und 20 Megapixel pro Bild, JPEG/PNG, normalisiert und ohne EXIF.
- Maximal 25 kostenpflichtige Modellaufrufe pro Sitzung, insgesamt 80 je Serverprozess. **Zusätzlich ein echtes Anbieter-Budgetlimit einrichten.**
- Keine dauerhafte Datenbank, kein produktiver Datenschutz-/Sicherheitsnachweis.

## Testen

~~~powershell
python -m pytest -q
python -m compileall -q app scripts
~~~

Die automatisierten Tests verwenden Mock/HTTP-Simulation und benötigen **keine** echten API-Schlüssel. Eine vollständige Abnahme mit tatsächlichem Gemini-Modell, Browser und synthetischen Handschriftfotos ist gesondert erforderlich.
