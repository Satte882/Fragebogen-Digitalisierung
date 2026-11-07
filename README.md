# Form Digitizer – Fragebogen-Digitalisierung

**Ausführbarer MVP (Stand: 07.11.2026), nicht produktionsreif.** Neutraler Prototyp zur Digitalisierung von Papierfragebögen. Fünf Ankreuzfragen (1–4) und ein Freitextfeld werden aus Fotos erfasst, bei Bedarf manuell geprüft und als **final bestätigte CSV** exportiert. Freitexte werden ins Deutsche übersetzt; es erfolgt **keine inhaltliche Analyse**.

> Öffentliches Testprojekt: Ausschließlich selbst erstellte oder synthetische Fotos verwenden. **Keine echten Kunden-, Firmen- oder Personendaten!** Bei OpenRouter-Nutzung gehen Bilder an einen externen KI-Dienst.

## Implementierte Funktionen

- Mehrfach- und Browser-Ordnerimport (JPEG/PNG), serverseitiger Verarbeitungslauf für 30 Bögen mit Fortschritt und Fehlerwiederholung, stabile Vorgangs- und Bild-IDs.
- Prüfwarteschlange, freiwillige Stichprobe und getrennte Herkunft von Sammelübernahme und Einzelprüfung.
- Dreispaltenansicht: Originalbild, unveränderte KI-Erkennung, finaler Datensatz. Grün = technische Prüfregeln bestanden, **keine 100-%-Garantie**. Unsichere Ergebnisse manuell prüfen und korrigieren.
- Eindeutig leere Felder als **Keine Antwort**; mehrere/unklare Kreuze werden nicht geraten. Wert nachtragen nur mit bestätigtem sichtbaren Beleg.
- Originalsprachige Transkription und Übersetzung nach Deutsch, ohne Glättung.
- CSV nur final bestätigte Werte und Zuordnungsdaten; **keine Roh-Erkennung im Export**.
- Login-Rollen **admin** und **test**: gleiche fachliche Funktionen; Admin zusätzlich Modell-Einstellungen. Der gemeinsame Testlogin erhält für jede Anmeldung einen **isolierten Arbeitsbereich**.
- OpenRouter-/Gemini-Adapter, Demo-Mock ohne externe API, drei **synthetische Fixbeispiele** (nicht als echte Modellleistung zu verstehen), Render-Konfiguration und automatisierte Tests.

## Lokal unter Windows starten

~~~powershell
git clone https://github.com/Satte882/Fragebogen-Digitalisierung.git
cd Fragebogen-Digitalisierung
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/bootstrap_local.py
python -m uvicorn app.main:app --reload
~~~

Im Browser **http://127.0.0.1:8000** öffnen. `bootstrap_local.py` erzeugt ein privates `.env` und zeigt einmalig zwei zufällige Passwörter für die Konten **admin** und **test**. Die Datei `.env` niemals in Git einchecken. Sollte PowerShell die Aktivierung verweigern, die Befehle mit `.\.venv\Scripts\python.exe` ausführen. Python 3.12+ erforderlich.

Unter **„Demo-Werkzeuge“ → „Neue Batch-Demo · 30 Bögen“** erscheint sofort ein Testvorgang mit 26 übernahmebereiten und vier zu prüfenden Bögen. Der Ablauf über Einzelprüfung, Sammelbestätigung und CSV benötigt dabei keine Anbieteraufrufe. Reguläre Uploads werden über **„Bögen erfassen“** verarbeitet. Eigene Foto-Uploads erhalten im Mock-Modus ausdrücklich **keine Schein-Erkennung**.

### Mit Gemini über OpenRouter

In der lokalen `.env` ergänzen und den Server neu starten:

~~~dotenv
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=DEIN_API_SCHLUESSEL
OPENROUTER_MODEL=google/gemini-2.5-flash
~~~

Die Modell-ID ist nur ein **Beispiel**. Vorher die Verfügbarkeit eines bildfähigen Gemini-Modells unter https://openrouter.ai/models prüfen. Es können API-Kosten entstehen. Standardmäßig gelten 100 Live-Aufrufe pro Sitzung und 250 pro Prozess. Auch Fehler und Wiederholungen zählen. Die Werte sind in der [.env-Vorlage](.env.example) dokumentiert. Ein Ausgabenlimit beim Anbieter bleibt sinnvoll. Die bisherige Live-Stichprobe umfasst nur drei synthetische Druckbögen.

Tests: `python -m pytest -q`.

## Render-Demo (optional)

Der [Render-Blueprint](render.yaml) enthält die Webservice-Konfiguration. Er benötigt im Render-Dashboard `ADMIN_PASSWORD_HASH` und `TEST_PASSWORD_HASH` (aus der lokalen `.env`, **Hashwerte statt Klartext**); `SESSION_SECRET` wird im Blueprint generiert. Optional für Live-Modelle: `OPENROUTER_API_KEY`, `MODEL_PROVIDER=openrouter` und `OPENROUTER_MODEL`. Standardmäßig startet die Demo **ohne KI** im Mock-Modus. **Render-Free ist flüchtig, kann schlafen und ist keine Produktionsumgebung.** Sitzungen und nicht exportierte Daten gehen beim Neustart verloren. Nur einen Worker betreiben; ohne Secrets bricht der Start absichtlich ab.

Ausführliche Hinweise: [Runbook](docs/RUNBOOK.md) · [Render Free](https://render.com/docs/free).

## Dokumentation

- [MVP-Anforderungen](docs/MVP.md)
- [Technische Architektur](docs/ARCHITECTURE.md)
- [Datenvertrag und CSV](docs/DATA_CONTRACT.md)
- [Testplan](docs/TEST_PLAN.md)
- [Roadmap](docs/ROADMAP.md)
- [Betriebshandbuch](docs/RUNBOOK.md)
- [Neutraler Musterfragebogen](examples/musterfragebogen.html)

**Pilotgrenze:** Keine produktive Datenschutz-/Sicherheitsfreigabe, keine dauerhafte Datenbank, kein Qualitätsversprechen über echte Handschriften. Automatisierte API-/Vertragstests prüfen die Software; eine echte Bildqualitätsabnahme mit OpenRouter-Schlüssel und selbst erstellten handschriftlichen Fotos steht noch aus.
