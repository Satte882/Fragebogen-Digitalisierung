from collections import Counter
from dataclasses import replace
import asyncio
import csv
import io
import time

import httpx
from fastapi.testclient import TestClient

from app.contracts import Recognition
from app.main import OpenRouterProvider, build_app
from app.providers import ProviderError
from scripts.evaluate_quality import score
from .conftest import login
from .test_api import picture, q_payload
from .test_provider import VALID_RESULT


def wait_run(client, url):
    for _ in range(250):
        status = client.get(url + "/process").json()
        if not status["run"]["active"]:
            return status
        time.sleep(.015)
    raise AssertionError("Batch timed out")


def test_thirty_images_deduplicate_retry_sample_and_export(monkeypatch, application):
    settings = replace(application.state.settings, model_provider="openrouter",
                       openrouter_api_key="test-only", openrouter_model="simulated")
    app = build_app(settings)
    calls = Counter()
    active = peak = 0

    async def recognize(self, image):
        nonlocal active, peak
        from PIL import Image
        with Image.open(io.BytesIO(image)) as photo:
            number = round(photo.getpixel((0, 0))[0] / 7)
        calls[number] += 1
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(.015)
            if number == 0 and calls[number] == 1:
                raise ProviderError("rate limited", code="rate_limit")
            if number == 1 and calls[number] == 1:
                raise ProviderError("timeout", code="timeout")
            if number == 2 and calls[number] == 1:
                raise ProviderError("invalid JSON")
            raw = dict(VALID_RESULT)
            if number >= 26:
                raw["q2"] = {"value": None, "status": "multiple"}
            return Recognition.model_validate(raw), "original"
        finally:
            active -= 1

    monkeypatch.setattr(OpenRouterProvider, "recognize", recognize)
    from PIL import Image
    files = []
    for number in range(30):
        buffer = io.BytesIO()
        Image.new("RGB", (60, 90), (number * 7, 30, 100)).save(buffer, "PNG")
        files.append(("images", (f"{number}.png", buffer.getvalue(), "image/png")))
    with TestClient(app) as c:
        headers = login(c)
        batch = c.post("/api/batches", headers=headers, data={"name": "30"}, files=files).json()
        url = f"/api/batches/{batch['id']}"
        first = c.post(url + "/process", headers=headers).json()
        second = c.post(url + "/process", headers=headers).json()
        assert first["run"]["id"] == second["run"]["id"]
        assert c.delete(url, headers=headers).status_code == 409
        status = wait_run(c, url)
        assert status["run"]["done"] == 30 and peak == 3
        assert status["budget"]["sent"] == 32 and status["budget"]["failed"] == 3
        assert status["items"][2]["error_code"] == "invalid_response"
        assert c.post(url + "/process?retry_failed=true", headers=headers).status_code == 202
        status = wait_run(c, url)
        assert status["run"]["total"] == 1 and status["ready"] == 26
        assert status["budget"] == dict(sent=33, succeeded=30, failed=3, repeated=3, remaining=67)
        sample = c.post(url + "/sample", headers=headers).json()
        picked = [x for x in sample["items"] if x["sample_selected"]]
        assert len(picked) == 5
        assert [x["id"] for x in c.post(url + "/sample", headers=headers).json()["items"]
                if x["sample_selected"]] == [x["id"] for x in picked]
        sample_url = f"{url}/items/{picked[0]['id']}"
        payload = q_payload(c.get(sample_url).json()["raw"], evidence=True)
        payload["q1"] = {"status": "answered", "value": 4}
        assert c.post(sample_url + "/confirm", headers=headers, json=payload).json()["sample_corrected"]
        bulk = c.post(url + "/confirm-ready", headers=headers).json()
        assert bulk["accepted"] == 25
        assert Counter(x["confirmation_source"] for x in bulk["batch"]["items"]) == {None: 4, "sample": 1, "bulk": 25}
        for item in bulk["batch"]["items"]:
            if item["status"] != "review_required":
                continue
            item_url = f"{url}/items/{item['id']}"
            assert c.post(item_url + "/review", headers=headers).status_code == 200
            raw = c.get(item_url).json()["raw"]
            assert c.post(item_url + "/confirm", headers=headers, json=q_payload(raw)).status_code == 200
            assert c.get(item_url).json()["raw_text"] == "original"
        exported = c.get(url + "/export.csv")
        rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig")), delimiter=";"))
        assert len(rows) == 30 and rows[-1]["q2_value"] == "" and rows[-1]["q2_status"] == "multiple"
        assert c.get(url + "/evaluation").json()["source"] == "live"
        assert c.post(url + "/process", headers=headers).status_code == 409
        with TestClient(app) as other:
            other_headers = login(other)
            assert other.get(url + "/process").status_code == 404
            assert other.post(url + "/process", headers=other_headers).status_code == 404
            assert other.get(url + "/evaluation").status_code == 404


def test_batch_demo_is_opt_in_and_uses_no_live_calls(application, monkeypatch):
    settings = replace(application.state.settings, model_provider="openrouter",
                       openrouter_api_key="test-only", openrouter_model="simulated")
    async def unexpected(self, image):
        raise AssertionError("Demo must not contact OpenRouter")
    monkeypatch.setattr(OpenRouterProvider, "recognize", unexpected)
    with TestClient(build_app(settings)) as client:
        headers = login(client)
        batch = client.post("/api/demo?full_batch=true", headers=headers).json()
        url = f"/api/batches/{batch['id']}"
        assert batch["synthetic"] and batch["count"] == 30
        assert batch["ready"] == 26 and batch["review_required"] == 4
        assert batch["run"] is None
        assert client.post(url + "/process", headers=headers).status_code == 409
        status = client.get(url + "/process").json()
        assert status["budget"]["sent"] == 0
        assert client.get(url + "/evaluation").json()["cases"] == []


def test_ready_demo_review_four_then_confirm_26_and_export(client):
    headers = login(client)
    batch = client.post("/api/demo?full_batch=true", headers=headers).json()
    url = f"/api/batches/{batch['id']}"
    assert batch["ready"] == 26 and batch["review_required"] == 4
    for item in batch["items"][-4:]:
        item_url = f"{url}/items/{item['id']}"
        before = client.get(item_url).json()
        payload = q_payload(before["raw"])
        assert payload["q2"] == {"status": "no_answer", "value": None}
        result = client.post(item_url + "/confirm", headers=headers, json=payload)
        assert result.json()["confirmation_source"] == "individual"
        assert client.get(item_url).json()["raw_text"] == before["raw_text"]
    partial = client.get(url + "/export.csv")
    assert (partial.headers["X-Exported-Count"], partial.headers["X-Unconfirmed-Count"]) == ("4", "26")
    bulk = client.post(url + "/confirm-ready", headers=headers).json()
    assert bulk["accepted"] == 26
    assert Counter(item["confirmation_source"] for item in bulk["batch"]["items"]) == {"bulk": 26, "individual": 4}
    complete = client.get(url + "/export.csv")
    csv_text = complete.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text), delimiter=";"))
    assert len(rows) == 30 and all(row["q2_value"] == "" for row in rows[-4:])
    assert "original_transcript" not in csv_text and "corrections" not in csv_text


def test_renaming_demo_batch_preserves_form_identity_in_csv(client):
    from app.export import COLUMNS

    headers = login(client)
    before = client.post("/api/demo?full_batch=true", headers=headers).json()
    url = f"/api/batches/{before['id']}"
    name = "Feedback Antalya – 02.05.2026"
    renamed = client.patch(url, headers=headers, json={"name": name})
    assert renamed.status_code == 200
    after = client.get(url).json()

    def identity(item):
        return item["id"], item["sequence"], item["filename"]

    assert (after["id"], after["name"]) == (before["id"], name)
    assert [identity(item) for item in after["items"]] == [identity(item) for item in before["items"]]
    assert [item["sequence"] for item in after["items"]] == list(range(1, 31))
    assert len({item["id"] for item in after["items"]}) == 30

    assert client.post(url + "/confirm-ready", headers=headers).json()["accepted"] == 26
    for item in after["items"][-4:]:
        route = f"{url}/items/{item['id']}"
        raw = client.get(route).json()["raw"]
        assert client.post(route + "/confirm", headers=headers, json=q_payload(raw)).status_code == 200

    exported = client.get(url + "/export.csv")
    reader = csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig")), delimiter=";")
    assert reader.fieldnames == COLUMNS
    rows = list(reader)
    assert {(row["batch_id"], row["batch_name"]) for row in rows} == {(before["id"], name)}
    assert [(row["image_id"], int(row["image_number"]), row["filename"]) for row in rows] == [
        identity(item) for item in before["items"]
    ]


def test_demo_image_30_keeps_visible_multiple_marks(client):
    headers = login(client)
    batch = client.post("/api/demo?full_batch=true", headers=headers).json()
    url = f"/api/batches/{batch['id']}"
    item = batch["items"][29]
    assert item["sequence"] == 30
    route = f"{url}/items/{item['id']}"
    before = client.get(route).json()
    payload = q_payload(before["raw"])
    payload["q4"] = {"status": "answered", "value": 3}
    assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 422
    assert client.get(route).json()["final"] is None
    assert client.post(route + "/confirm", headers=headers, json=q_payload(before["raw"])).status_code == 200
    assert client.get(url + "/corrections").json() == {"changes": []}
    rows = list(csv.DictReader(io.StringIO(client.get(url + "/export.csv").content.decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 1 and rows[0]["q4_value"] == "" and rows[0]["q4_status"] == "multiple"


def test_justified_correction_is_private_and_only_latest_final_is_shown(application, monkeypatch):
    from app.demo import FIXTURES, demo_photo
    from app.export import COLUMNS
    from app.providers import MockProvider

    async def recognize(self, image):
        return Recognition.model_validate(FIXTURES[1]["recognition"]), "unchanged mock output"

    monkeypatch.setattr(MockProvider, "recognize", recognize)
    values = [2, None, 3, 3, 1]
    photo = demo_photo(values, "")
    with TestClient(application) as client, TestClient(application) as outsider:
        headers = login(client)
        login(outsider)
        batch = client.post("/api/batches", headers=headers, data={"name": "Correction"},
                            files={"images": ("evidence.jpg", photo, "image/jpeg")}).json()
        url = f"/api/batches/{batch['id']}"
        route = f"{url}/items/{batch['items'][0]['id']}"
        assert client.post(route + "/recognize", headers=headers).status_code == 200
        before = client.get(route).json()
        payload = q_payload(before["raw"], evidence=True)
        payload["q4"] = {"status": "answered", "value": 3}
        payload["multiple_reasons"] = {"q4": "Nur Kästchen 3 enthält ein Kreuz. Kästchen 2 ist leer."}
        payload["evidence_confirmed"] = False
        assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 422
        payload["evidence_confirmed"] = True
        assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 200
        assert client.get(url + "/corrections").json()["changes"] == [{
            "sequence": 1, "field": "q4", "before": before["raw"]["q4"],
            "after": payload["q4"], "reason": payload["multiple_reasons"]["q4"],
        }]
        assert outsider.get(url + "/corrections").status_code == 404
        assert client.get(route).json()["raw_text"] == before["raw_text"]
        result = client.get(url + "/export.csv").content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(result), delimiter=";")
        assert reader.fieldnames == COLUMNS and next(reader)["q4_value"] == "3"
        assert "Kästchen" not in result and "mock output" not in result
        assert client.post(route + "/reopen", headers=headers).status_code == 200
        assert client.get(url + "/corrections").json() == {"changes": []}
        assert client.post(route + "/confirm", headers=headers, json=q_payload(before["raw"])).status_code == 200
        assert client.get(url + "/corrections").json() == {"changes": []}
        assert len(client.get(route).json()["corrections"]) == 1
        assert client.post(route + "/reopen", headers=headers).status_code == 200
        payload["multiple_reasons"] = {"q4": "   "}
        assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 200
        assert client.get(url + "/corrections").json()["changes"][0]["reason"] is None


def test_ground_truth_exposes_false_green_and_detected_warnings():
    expected = {"schema_version": 1, "cases": [
        {"id": str(i), "requires_review": i == 1, "answers": {q: VALID_RESULT[q] for q in ("q1","q2","q3","q4","q5")},
         **{k: VALID_RESULT["text"][k] for k in ("original_transcript","german_translation","text_status")}}
        for i in range(2)
    ]}
    observed = {"source": "live", "cases": [
        {"id": "0", "classification": "ready", "recognition": {**VALID_RESULT, "q1": {"value": 4, "status": "answered"}},
         "confirmation_source": "bulk", "review_mode": "unchanged", "runs": []},
        {"id": "1", "classification": "review_required", "recognition": VALID_RESULT,
         "confirmation_source": "individual", "review_mode": "corrected", "runs": []},
    ]}
    result = score(expected, observed)
    assert result["false_green"] == 1 and result["green"] == 1
    assert result["field_hits"] == 9 and result["fields"] == 10
    assert result["complete_hits"] == 1 and result["warnings_detected"] == 1
    assert result["individually_reviewed"] == 1 and result["corrected"] == 1
