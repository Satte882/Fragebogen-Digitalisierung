from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.contracts import Recognition
from app.demo import BLANK_FORM, EXAMPLE_FORMS, HANDWRITING_FORMS
from app.main import OpenRouterProvider, build_app
from scripts.evaluate_quality import score
from .conftest import login
from .test_api import q_payload
from .test_provider import VALID_RESULT


def test_example_assets_are_metadata_free_and_have_separate_ground_truth():
    reference = json.loads(Path("docs/handwriting-ground-truth.json").read_text(encoding="utf-8"))
    assert [case["id"] for case in reference["cases"]] == list(HANDWRITING_FORMS)
    for name in (*HANDWRITING_FORMS, BLANK_FORM):
        with Image.open(EXAMPLE_FORMS / name) as form:
            assert form.format == "PNG" and not form.info and not form.getexif()


def test_examples_require_login_and_cannot_use_mock(client):
    assert client.get("/api/examples/blank-form").status_code == 401
    assert client.post("/api/examples/handwriting").status_code == 401
    headers = login(client)
    blank = client.get("/api/examples/blank-form")
    assert blank.status_code == 200 and blank.headers["content-type"] == "image/png"
    assert blank.content == (EXAMPLE_FORMS / BLANK_FORM).read_bytes()
    assert client.post("/api/examples/handwriting").status_code == 403
    batch = client.post("/api/examples/handwriting", headers=headers).json()
    assert not batch["synthetic"]
    assert [item["filename"] for item in batch["items"]] == list(HANDWRITING_FORMS)
    assert all(item["source"] == "handwriting_example" and item["status"] == "pending" for item in batch["items"])
    route = f"/api/batches/{batch['id']}"
    assert client.post(route + "/process", headers=headers).status_code == 409
    assert client.post(f"{route}/items/{batch['items'][0]['id']}/recognize", headers=headers).status_code == 409
    assert client.get("/api/me").json()["budget"]["sent"] == 0


def test_examples_use_live_adapter_with_fresh_isolated_state_and_limits(application, monkeypatch):
    calls = []

    async def recognize(self, image):
        with Image.open(BytesIO(image)) as normalized:
            assert normalized.format == "JPEG"
        calls.append(image)
        return Recognition.model_validate(VALID_RESULT), json.dumps(VALID_RESULT)

    monkeypatch.setattr(OpenRouterProvider, "recognize", recognize)
    app = build_app(replace(application.state.settings, model_provider="openrouter",
                            openrouter_api_key="test-only", openrouter_model="simulated",
                            live_calls_per_session=1, max_images_per_session=5))
    with TestClient(app) as tester, TestClient(app) as admin:
        test_headers, admin_headers = login(tester), login(admin, "admin")
        one = tester.post("/api/examples/handwriting", headers=test_headers).json()
        two = admin.post("/api/examples/handwriting", headers=admin_headers).json()
        assert tester.post("/api/examples/handwriting", headers=test_headers).status_code == 429
        assert one["id"] != two["id"]
        assert {item["id"] for item in one["items"]}.isdisjoint(item["id"] for item in two["items"])
        assert calls == []
        batch_route = f"/api/batches/{one['id']}"
        item_route = f"{batch_route}/items/{one['items'][0]['id']}"
        assert admin.get(batch_route).status_code == 404
        assert tester.get(item_route).json()["raw"] is None
        assert tester.post(item_route + "/recognize", headers=test_headers).status_code == 200
        assert tester.post(batch_route + "/process", headers=test_headers).status_code == 429
        assert len(calls) == 1
        recognized = tester.get(item_route).json()
        assert recognized["source"] == "handwriting_example"
        assert tester.post(item_route + "/confirm", headers=test_headers,
                           json=q_payload(recognized["raw"])).status_code == 200
        snapshot = tester.get(batch_route + "/evaluation").json()
        case, = snapshot["cases"]
        assert case["recognition"] == recognized["raw"] and case["final"]
        assert "recognition" not in tester.get(batch_route + "/export.csv").text
        assert all(item["status"] == "pending" for item in admin.get(f"/api/batches/{two['id']}").json()["items"])

        reference = {"schema_version": 1, "id_kind": "filename", "cases": [{
            "id": case["filename"], "requires_review": False,
            "answers": {f"q{i}": VALID_RESULT[f"q{i}"] for i in range(1, 6)},
        }]}
        comparison = score(reference, snapshot)
        assert comparison["field_hits"] == comparison["final_field_hits"] == 5
