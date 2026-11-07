# Technisches Konzept – MVP

**Status:** Architekturentscheidung, noch nicht implementiert.

## Systemgrenze

Die Webanwendung wird lokal auf Windows entwickelt und später ggf. als einzelner Python-Webservice auf Render bereitgestellt. **Lokale Ausführung des Webservers ist nicht lokale KI-Verarbeitung.** Beim gewählten OpenRouter-Adapter werden Bilddaten an einen externen API-Dienst gesendet. Deshalb: **ausschließlich selbst erzeugte oder ausdrücklich freigegebene synthetische Testbilder**.

## Bausteine

1. **Web-UI:** Upload eines Ordners bzw. mehrerer JPEG/PNG, Vorgangsmetadaten, Bildstatus, Dreispaltenprüfung, finaler Export.
2. **FastAPI-Backend:** Login, Rollen und Sitzung, Upload-/Dateiprüfung, Erkennungsaufträge, Validierung, Status, CSV-Generierung.
3. **Model-Adapter:** Einheitlicher Programmvertrag für multimodale Modelle; zunächst OpenRouter/Gemini, zukünftig weitere Endpunkte. Keine Anbieterlogik in den Fachregeln.
4. **Parser/Validator:** Modellantwort nach vorgegebenem Datenschema auf Typen, erlaubte Werte und konsistente Feldstatus prüfen; Verdachtsfälle markieren, nicht überschreiben.
5. **Arbeitsbereichsspeicher:** Server-seitige, kurzlebige Vorgangs-/Bild-/Ergebnisdaten pro Sitzung. Kein dauerhaftes Geschäftsdaten-Repository im MVP.
6. **Demo-Fixdaten:** Neutraler Musterfragebogen mit synthetischen Beispielantworten, auch ohne API-Aufruf zugänglich.

## Datenfluss

Browser (angemeldet)
→ Sitzung / isolierter Vorgang
→ JPG/PNG-Upload
→ OpenRouter-Model-Adapter
→ strukturierte KI-Roh-Erkennung
→ Schema- und Plausibilitätsprüfung
→ Status: Übernahmebereit oder Prüfung erforderlich
→ fachliche Bestätigung/Korrektur in der UI
→ **nur finale Daten** in CSV.

Die Rohantwort bleibt bis zum Sitzungsende intern zum Vergleich verfügbar; sie wird weder als CSV exportiert noch versehentlich in öffentliche Logs geschrieben. Eine externe Datenbank ist in Phase 1 nicht vorgesehen.

## Modelladapter

Schnittstelle auf fachlicher Ebene:

- Eingang: Bildbytes oder Bildreferenz (nur innerhalb der Sitzung), Formulartyp/-version, feste Fragen-IDs, erwartete Skala, Anweisung zur Handschrifttranskription und Übersetzung.
- Ausgang: Formularversion, Werte/Status je Frage, Originaltranskript, deutsche Übersetzung, markierte Unsicherheiten/Lesbarkeitsprobleme, ggf. technische Fehler.
- Die Anwendung validiert das Modellresultat **separat**. Der Modelladapter darf keine endgültige menschliche Bestätigung setzen.
- Ein Wechsel des Adapters verändert weder Oberfläche noch CSV-Vertrag. **Modellwechsel bedeutet dennoch erneute Qualitätsevaluation**; gleiche API-Struktur garantiert nicht gleiche Erkennungsleistung.
- Modellname über Konfiguration; keine harte Zusage, dass ein bestimmtes proprietäres Modell lokal betrieben werden kann.
- API-Schlüssel ausschließlich im Backend als Secret, niemals an Browser oder Repository ausgeben.

## Qualitäts- und Statuslogik

**Grün** bedeutet nur:
- syntaktisch gültige Antwort zum erwarteten Schema;
- alle Fragen haben einen zulässigen Werte- oder Leerstelle-Status;
- keine erkannten Mehrfachmarkierungen, fehlgeschlagene Transkriptionen oder sonstigen Warnsignale;
- keine Modell-/Parserwarnungen.

Diese Prüfungen garantieren **keine 100-prozentige visuelle Korrektheit**. Für die Pilot-Evaluation werden systematisch bekannte Testantworten mit dem KI-Ergebnis und den bestätigten Korrekturen verglichen.

**Gelb**: mindestens ein unklarer oder widersprüchlicher Befund; fachlicher Prüfschritt erforderlich.

**Rot**: technischer Fehler / nicht auswertbares Bild; erneuter Versuch oder dokumentierter Abbruch.

**Final**: Mensch hat alle Felder bestätigt, einschließlich expliziter leerer/ungültiger Antworten. Nicht „final“ mit „grün“ gleichsetzen.

## Sitzungs- und Sicherheitskonzept

- Zwei **Rollen**: Admin und Test. Beide haben gleiche fachliche Funktionen. **Nur Admin** darf Modellkonfiguration/technische Einstellungen ändern.
- Geteiltes Testkonto, aber **isolierter Arbeitsbereich pro Login-Sitzung** mit kryptografisch zufälliger Kennung. Jeder API-Zugriff auf Vorgänge und Bilder erzwingt Sitzungszuordnung **serverseitig**.
- Login-Credentials als Hashes/Secrets aus Umgebungsvariablen oder Secret-Store; niemals Klartext-Passwörter in Quellcode, Git, HTML oder Client-Konfiguration.
- Serverseitige Session; Cookie mit HttpOnly, Secure (HTTPS), geeignetem SameSite; Ablauf und explizites Logout. CSRF-Schutz für zustandsändernde Cookie-Requests, Login-Rate-Limit.
- Uploadlimits: Anzahl und Größe begrenzen; tatsächlichen Dateityp prüfen; keine beliebigen Pfade, Dateinamen normalisieren; Bild-Metadaten/EXIF nicht öffentlich weiterreichen.
- Geheimnisse, Bilder und Rohantworten niemals in Anwendungslogs ausgeben.
- Zugriffe der Testnutzer begrenzen, um unkontrollierte externe API-Kosten zu verhindern (z. B. Bilder/Sitzung, Rate-Limit, Timeout).
- Sitzung nach Ablauf **nicht rekonstruierbar**. Das UI warnt vor Datenverlust und bietet CSV-Download. Keine Versprechen über dauerhaftes Speichern.
- Da der Dienst bei kostenlosem Hosting neu starten kann, sind rein serverbasierte Live-Arbeitsbereiche **nicht** dauerhaft verfügbar. Synthetische Demo-Fixdaten aus dem Repository bleiben verfügbar.

## Deployment – erst später

- Lokale Entwicklung: Windows + Python + FastAPI; Secret via lokale, ignorierte **.env**.
- Render: Webservice mit sicherem HTTPS-Zugang, passenden Umgebungsvariablen, Prozessbindung an **0.0.0.0** und **PORT**. Repo allein erzeugt **noch keinen** lauffähigen Render-Dienst.
- Render Free: bei Inaktivität mögliche Unterbrechung und flüchtiges Dateisystem. Daher kein Archiv und kein langfristiger Uploadspeicher. Die Plattformgrenzen vor Deployment erneut überprüfen: https://render.com/docs/free
- OpenRouter API und Hosting sind unterschiedliche Dienste; für Modell-API-Aufrufe können trotz kostenlosen Hostings Kosten entstehen.
- Demo und echte Daten strikt trennen. Nicht als produktionsgeeignete Datenschutz-/Sicherheitslösung ausgeben.

## Bewusst nicht vorgesehen

Datenbank, Wiederaufnahme über mehrere Tage, Benutzerregistrierung, Single-Sign-On, zentrale Revisionshistorie, automatische Formularanalyse, unbegrenzte Bildverarbeitung, generische Formularerkennung, Nutzung echter Kundendaten.

## Bevorzugte Implementierungsreihenfolge

1. Schema und synthetische Daten/Tests.
2. Upload, Vorgangslogik, Bildansicht und Mock-Adapter ohne externe Kosten.
3. OpenRouter-Adapter mit kontrollierten Modellaufrufen.
4. Plausibilitätsprüfung und interaktive menschliche Bestätigung.
5. CSV-Export und messbare Testfälle.
6. Authentifizierung, Sitzungsisolation und Security-Checks **vor** öffentlichem Deployment.
7. Render-Demo.
