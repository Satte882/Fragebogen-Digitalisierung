# Datenvertrag: Erkennung, Prüfung und CSV

**Version:** 0.1 (konzeptionell) · **Status:** noch nicht implementiert

## Kernprinzipien

- **Ein Vorgang** (batch) enthält mehrere hochgeladene **Formularbilder** (items).
- Jeder Vorgang erhält eine stabile generierte Vorgangs-ID und einen bearbeitbaren Namen.
- Je Bild existieren **KI-Roh-Erkennung** und **finaler bestätigter Datensatz** getrennt. Nur Letzterer darf in die CSV.
- Keine inhaltliche Analyse; die deutsche Freitextfassung ist eine **Übersetzung**, kein geglätteter oder bewerteter Text.
- Es gibt genau fünf Frage-IDs: **q1 bis q5**; jede zulässige Antwort ist eine Ganzzahl aus **1, 2, 3, 4** oder **leer mit explizitem Status**.

## Feldebene

Bewertungsfrage:

| Feld | Typ / Regel |
| --- | --- |
| value | int 1–4 oder null |
| status | answered / no_answer / multiple / unreadable |
| warning | optional, nur intern zur Prüfung |
| source_question | q1 bis q5, unverändert |

Konsistenzregeln:
- **answered** erfordert einen ganzzahligen Wert 1–4.
- **no_answer**: Wert null; kein sichtbares Kreuz.
- **multiple**: Wert null; mehrere widersprüchliche Markierungen.
- **unreadable**: Wert null; aus dem Bild nicht sicher zuordenbar.
- Ein Prüfer darf **no_answer** oder **multiple** nicht ohne sichtbaren Beleg in einen geratenen Skalenwert umwandeln.

Freitext:
- **original_transcript**: möglichst wortgetreue, originalsprachige Transkription (nur intern/UI).
- **source_language**: festgestellte Originalsprache oder „unknown“ (intern).
- **german_translation**: deutsche Übersetzung, wenn hinreichend sicher.
- **text_status**: translated / empty / unreadable / review_required.
- Unlesbares, unvollständiges oder schlecht übersetzbares Material wird gekennzeichnet; keine erdachten Sätze ergänzen.

## Beispiel des internen Zwischendatensatzes

Die nachfolgende Struktur illustriert den **Vertrag**, nicht eine bereits programmierte API.

~~~json
{
  "schema_version": "0.1",
  "form_version": "fixed-5x4-v1",
  "batch": {
    "id": "48df5801-2f5b-4f3b-8b0c-72a28086e9b0",
    "name": "Veranstaltung Nord – 02.05.2026"
  },
  "item": {
    "id": "f4af3744-4a92-405b-8242-66989f55ad4b",
    "sequence": 1,
    "filename": "formular_01.jpg",
    "review_status": "review_required",
    "questions": {
      "q1": {"value": 4, "status": "answered"},
      "q2": {"value": 3, "status": "answered"},
      "q3": {"value": null, "status": "no_answer"},
      "q4": {"value": 2, "status": "answered"},
      "q5": {"value": 4, "status": "answered"}
    },
    "text": {
      "original_transcript": "Everything was well organized.",
      "source_language": "en",
      "german_translation": "Alles war gut organisiert.",
      "text_status": "translated"
    }
  }
}
~~~

**Achtung:** Der gesamte Zwischendatensatz ist **intern**. Erst nach der fachlichen Bestätigung wird ein **separater Exportdatensatz** erzeugt. Die Felder original_transcript, source_language, alle Modellwarnungen und die ursprüngliche KI-Rohantwort werden **nicht** als CSV-Spalten aufgenommen.

## CSV-Vertrag – nur bestätigte Datensätze

**Eine Zeile = ein bestätigtes Bild/Formular.**

Spalten in fester Reihenfolge:

1. **batch_id** – stabile Vorgangs-ID.
2. **batch_name** – aktuell bestätigter Vorgangsname.
3. **image_id** – stabile Bild-ID.
4. **image_number** – laufende Bildnummer im Vorgang.
5. **filename** – ursprünglicher Dateiname, sicher escaped.
6. **q1_value**, **q1_status**.
7. **q2_value**, **q2_status**.
8. **q3_value**, **q3_status**.
9. **q4_value**, **q4_status**.
10. **q5_value**, **q5_status**.
11. **text_de** – **nur** deutsche bestätigte Übersetzung, keine Rohtranskription.
12. **text_status** – translated / empty / unreadable.
13. **review_mode** – unchanged / corrected.
14. **review_status** – confirmed.

**CSV-Technik:** UTF-8 mit BOM, Semikolon-Trennzeichen (deutsche Excel-Voreinstellung), sauber gequotete Sonderzeichen und Zeilenumbrüche. Kein Formelfeld darf als Excel-Formel ausgeführt werden; mit =, +, - oder @ beginnende freie Texte müssen beim CSV-Schreiben gegen CSV-Formelinjektion geschützt werden, ohne den inhaltlichen Wert im internen Datensatz zu verändern.

**Leere Werte:** Ist q3_status = no_answer, wird q3_value als leeres CSV-Feld geschrieben, nicht als 0, 1 oder erfundene Antwort. Gleiches Prinzip für multiple und unreadable.

**Exportselektion:** Nur Elemente mit review_status = confirmed. Bei unbestätigten Bildern zeigt das UI explizit deren Anzahl. Die normalen CSVs enthalten keine Modellprompts, Tokens, Rohantworten, personenbezogenen Anmeldeinformationen, Dateipfade oder Bildbytes.

## Interne Evaluationsdaten

Für einen kontrollierten Pilotversuch darf die Anwendung **innerhalb der laufenden Sitzung** eine differenzierte Gegenüberstellung zeigen: Modellvorschlag versus menschliche Bestätigung versus bekannter synthetischer Sollwert. Diese Vergleichsdaten sind **kein Bestandteil des regulären CSV-Exports** und werden bei Sitzungsende verworfen.

## Spätere Datenbankfähigkeit

batch_id und image_id erlauben spätere Tabellen für Vorgänge, Formularbilder, Antworten und Freitexte. Eine Datenbank ist für den MVP **nicht** vorgesehen. Der CSV-Vertrag bleibt absichtlich unabhängig vom Backend.
