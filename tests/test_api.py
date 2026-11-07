from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import csv
import io
import httpx
import pytest

from app.config import Settings
from app.main import MockProvider, OpenRouterProvider, build_app
from app.providers import ProviderError
from app.security import password_hash
from PIL import Image
from fastapi.testclient import TestClient

from .conftest import login


def picture(fmt='JPEG'):
    image = Image.new('RGB', (120,180),'white')
    buf=BytesIO(); image.save(buf,format=fmt)
    return buf.getvalue()


def q_payload(raw, *, text_status=None, text_de=None, evidence=False):
    payload={f'q{i}': raw[f'q{i}'] for i in range(1,6)}
    payload['text']={
        'german_translation': raw['text']['german_translation'] if text_de is None else text_de,
        'text_status': raw['text']['text_status'] if text_status is None else text_status,
    }
    payload['evidence_confirmed']=evidence
    return payload


def test_no_auth_health_and_login_protection(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/health').json()['status'] == 'ok'
    assert client.get('/openapi.json').status_code == 404
    assert client.get('/api/batches').status_code == 401
    assert client.post('/api/login', json={'username':'test','password':'wrong'}).status_code == 401
    head=login(client)
    assert client.get('/api/me').json()['role']=='test'
    assert client.post('/api/demo').status_code==403  # CSRF required
    assert client.get('/api/admin/config').status_code==403
    assert client.post('/api/admin/config',headers=head,json={'provider':'mock'}).status_code==403
    assert client.post('/api/logout',headers=head).status_code==200
    assert client.get('/api/me').status_code==401


def test_admin_configuration(client):
    head=login(client, 'admin')
    result=client.get('/api/admin/config').json()
    assert result['provider']=='mock' and not result['openrouter_key_configured']
    assert client.post('/api/admin/config',headers=head,json={'provider':'openrouter','model':'google/gemini-2.5-flash'}).status_code==422
    assert client.post('/api/admin/config',headers=head,json={'provider':'mock'}).status_code==200


def test_demo_workflow_and_csv_export(client):
    head=login(client)
    demo=client.post('/api/demo',headers=head)
    assert demo.status_code==200
    batch=demo.json()
    assert batch['synthetic'] and batch['count']==3
    assert batch['ready']==1 and batch['review_required']==2
    assert batch['items'][1]['findings'][0]['field'] == 'q4'
    assert batch['items'][2]['findings'][0]['kind'] == 'demo'
    assert batch['items'][2]['findings'][0]['field'] == 'text'
    batchid=batch['id']; imageid=batch['items'][0]['id']
    detail=client.get(f'/api/batches/{batchid}/items/{imageid}').json()
    assert detail['raw']['q1']['value']==4
    assert detail['raw']['text']['german_translation']=='Alles war gut organisiert.'
    assert detail['source']=='synthetic_demo'
    preview = client.get(f'/api/batches/{batchid}/items/{imageid}/thumbnail')
    assert preview.status_code == 200
    with Image.open(BytesIO(preview.content)) as thumb:
        assert max(thumb.size) <= 160
    assert detail['image_url'].startswith('data:image/jpeg;base64,')
    assert client.post(f'/api/batches/{batchid}/items/{imageid}/recognize',headers=head).status_code==409
    assert client.get(f'/api/batches/{batchid}/export.csv').status_code==409
    bulk=client.post(f'/api/batches/{batchid}/confirm-ready',headers=head)
    assert bulk.status_code==200 and bulk.json()['accepted']==1
    # Redundant bulk confirm is idempotent.
    assert client.post(f'/api/batches/{batchid}/confirm-ready',headers=head).json()['accepted']==0
    image2=batch['items'][1]['id']
    second=client.get(f'/api/batches/{batchid}/items/{image2}').json()
    raw=second['raw']; assert raw['q2']['status']=='no_answer'
    endpoint=f'/api/batches/{batchid}/items/{image2}'
    payload=q_payload(raw)
    assert client.post(endpoint+'/confirm',headers=head,json=payload).status_code==200
    res=client.get(f'/api/batches/{batchid}/export.csv')
    assert res.status_code==200
    assert res.content[:3]==b'\xef\xbb\xbf'
    assert res.headers['X-Exported-Count']=='2'
    assert res.headers['X-Unconfirmed-Count']=='1'
    csvout=res.content.decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(csvout),delimiter=';'))
    assert len(rows)==2
    assert rows[1]['q2_status']=='no_answer'
    assert rows[1]['q2_value']==''
    assert rows[0]['text_de']=='Alles war gut organisiert.'
    assert 'original_transcript' not in csvout
    assert 'Everything was well organized' not in csvout
    assert 'source_language' not in csvout
    # Rename updates exported metadata.
    assert client.patch(f'/api/batches/{batchid}',headers=head,json={'name':'Beispiel Mai 2026'}).status_code==200
    renewed=client.get(f'/api/batches/{batchid}/export.csv').content.decode('utf-8-sig')
    assert 'Beispiel Mai 2026' in renewed


def test_reopen_and_reconfirm(client):
    head=login(client)
    batch=client.post('/api/demo',headers=head).json();bid=batch['id'];iid=batch['items'][0]['id']
    client.post(f'/api/batches/{bid}/confirm-ready',headers=head)
    route=f'/api/batches/{bid}/items/{iid}'
    assert client.post(route+'/reopen',headers=head).status_code==200
    detail=client.get(route).json()
    assert detail['draft']['q1']['value']==4
    assert detail['review_started'] and detail['status']=='review_required'
    assert client.get(f'/api/batches/{bid}/export.csv').status_code==409
    payload=q_payload(detail['draft'])
    payload['q1']={'value':3,'status':'answered'}
    assert client.post(route+'/confirm',headers=head,json=payload).status_code==422
    payload['evidence_confirmed']=True
    assert client.post(route+'/confirm',headers=head,json=payload).status_code==200
    assert client.get(route).json()['review_mode']=='corrected'


def test_evidence_required_to_fill_originally_blank(client):
    head=login(client)
    batch=client.post('/api/demo',headers=head).json();bid=batch['id'];iid=batch['items'][1]['id']
    route=f'/api/batches/{bid}/items/{iid}'
    raw=client.get(route).json()['raw']
    client.post(route+'/review',headers=head)
    bad=q_payload(raw);bad['q2']={'status':'answered','value':4}
    assert client.post(route+'/confirm',headers=head,json=bad).status_code==422
    bad['evidence_confirmed']=True
    assert client.post(route+'/confirm',headers=head,json=bad).status_code==200


@pytest.mark.parametrize("field,target", [("q1", 3), ("q2", 3), ("q4", 3), ("unreadable", 3)])
def test_attestation_required_without_review_start_and_audit_is_private(client, field, target):
    headers = login(client)
    if field == "unreadable":
        batch = client.post("/api/batches", headers=headers, data={"name":"unreadable"},
                            files={"images": ("photo.jpg", picture(), "image/jpeg")}).json()
        item_id = batch["items"][0]["id"]
        route = f"/api/batches/{batch['id']}/items/{item_id}"
        assert client.post(route + "/recognize", headers=headers).status_code == 200
        field = "q1"
        text_status = "empty"
    else:
        batch = client.post("/api/demo", headers=headers).json()
        route = f"/api/batches/{batch['id']}/items/{batch['items'][1]['id']}"
        text_status = None
    before = client.get(route).json()
    payload = q_payload(before["raw"], text_status=text_status)
    payload[field] = {"value":target, "status":"answered"}
    assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 422
    rejected = client.get(route).json()
    assert rejected["final"] is None and rejected["corrections"] == []
    payload["evidence_confirmed"] = True
    assert client.post(route + "/confirm", headers=headers, json=payload).status_code == 200
    after = client.get(route).json()
    assert after["raw_text"] == before["raw_text"] and after["raw"] == before["raw"]
    audit = after["corrections"][0]
    expected_fields = [field, "text"] if text_status else [field]
    assert audit["fields"] == expected_fields and audit["attested_by_role"] == "test"
    assert audit["before"][field] == before["raw"][field]
    assert audit["after"][field] == payload[field]
    exported = client.get(f"/api/batches/{batch['id']}/export.csv").text
    assert "attested" not in exported and "corrections" not in exported


def test_delete_only_owned_batch_and_keep_other_data(application):
    with TestClient(application) as owner, TestClient(application) as outsider:
        own_headers = login(owner)
        outside_headers = login(outsider)
        first = owner.post("/api/demo", headers=own_headers).json()
        second = owner.post("/api/demo", headers=own_headers).json()
        route = f"/api/batches/{first['id']}"
        assert outsider.delete(route, headers=outside_headers).status_code == 404
        assert owner.delete(route).status_code == 403
        assert owner.delete(route, headers=own_headers).status_code == 204
        assert owner.get(route).status_code == 404
        assert [item["id"] for item in owner.get("/api/batches").json()] == [second["id"]]


def test_browser_provider_guard_rejects_stale_mode(client):
    headers = login(client)
    batch = client.post("/api/batches", headers=headers, data={"name":"pending"},
                        files={"images":("photo.jpg", picture(), "image/jpeg")}).json()
    route = f"/api/batches/{batch['id']}/process"
    assert client.post(route + "?expected_provider=openrouter", headers=headers).status_code == 409
    assert client.get(route).json()["run"] is None


def test_upload_and_mock_recognition(client):
    head=login(client)
    upload=client.post('/api/batches',headers=head,data={'name':' Event A '},files=[
        ('images',('form_1.jpg', picture(), 'image/jpeg')),
        ('images',('form_2.png', picture('PNG'), 'image/png')),
    ])
    assert upload.status_code==200, upload.text
    batch=upload.json();bid=batch['id']; iid=batch['items'][0]['id']
    assert batch['name']=='Event A' and batch['count']==2
    route=f'/api/batches/{bid}/items/{iid}'
    result=client.post(route+'/recognize',headers=head)
    assert result.status_code==200
    assert result.json()['status']=='review_required'
    raw=client.get(route).json()['raw']
    assert 'DEMO-MODUS' in raw['warnings'][0]
    # Manually transcribe a visible answer, but require explicit evidence attestation.
    client.post(route+'/review',headers=head)
    payload=q_payload(raw,text_status='empty',text_de='',evidence=True)
    payload['q1']={'value':2,'status':'answered'}
    assert client.post(route+'/confirm',headers=head,json=payload).status_code==200
    rows=list(csv.DictReader(io.StringIO(client.get(f'/api/batches/{bid}/export.csv').content.decode('utf-8-sig')),delimiter=';'))
    assert rows[0]['q1_value']=='2' and rows[0]['review_mode']=='corrected'


def test_bad_images_and_upload_limits(client):
    head=login(client)
    invalid=client.post('/api/batches',headers=head,data={'name':'bad'},files=[('images',('bad.jpg',b'not an image','image/jpeg'))])
    assert invalid.status_code==400
    badformat=client.post('/api/batches',headers=head,data={'name':'bad'},files=[('images',('bad.exe',picture(),'application/octet-stream'))])
    assert badformat.status_code==400
    good=client.post('/api/batches',headers=head,data={'name':'okay'},files=[('images',('good.jpg',picture(),'image/jpeg'))])
    assert good.status_code==200
    batch=good.json()
    assert client.get('/api/batches/'+batch['id']).status_code==200
    assert client.patch('/api/batches/'+batch['id'],headers=head,json={'name':''}).status_code==422
    oversized = client.post('/api/batches', headers=head, data={'name': 'Too large'},
                            files={'images': ('huge.jpg', b'x' * (10 * 1024 * 1024 + 1), 'image/jpeg')})
    assert oversized.status_code == 413
    too_many = client.post('/api/batches', headers=head, data={'name': 'Too many'},
                           files=[('images', ('a.jpg', picture(), 'image/jpeg'))] * 41)
    assert too_many.status_code == 400


def test_same_login_isolation(application):
    with TestClient(application) as first, TestClient(application) as second:
        first_headers=login(first,'test')
        second_headers=login(second,'test')
        one=first.post('/api/demo',headers=first_headers).json()
        bid=one['id']; iid=one['items'][0]['id']
        assert second.get('/api/batches').json()==[]
        assert second.get(f'/api/batches/{bid}').status_code==404
        assert second.get(f'/api/batches/{bid}/items/{iid}').status_code==404
        assert second.get(f'/api/batches/{bid}/items/{iid}/thumbnail').status_code==404
        assert second.post(f'/api/batches/{bid}/confirm-ready',headers=second_headers).status_code==404
        assert second.get(f'/api/batches/{bid}/export.csv').status_code==404
        assert first.get(f'/api/batches/{bid}/items/{iid}').status_code==200


def test_cross_site_cookie_csrf_and_invalid_confirmation(client):
    head=login(client)
    batch=client.post('/api/demo',headers=head).json();bid=batch['id'];iid=batch['items'][0]['id']
    route=f'/api/batches/{bid}/items/{iid}'
    assert client.post(route+'/review',headers={'x-csrf-token':'invalid'}).status_code==403
    assert client.post(route+'/review', headers={'x-csrf-token': '\u00e4'.encode()}).status_code == 403
    raw=client.get(route).json()['raw']
    invalid=q_payload(raw);invalid['q1']={'value':5,'status':'answered'}
    assert client.post(route+'/confirm',headers=head,json=invalid).status_code==422
    invalid=q_payload(raw);invalid['text']={'german_translation':'made up','text_status':'empty'}
    assert client.post(route+'/confirm',headers=head,json=invalid).status_code==422


def test_mixed_upload_preserves_good_image_and_applies_exif_rotation(client):
    headers = login(client)
    photo = Image.new("RGB", (2000, 1000), "white")
    exif = Image.Exif()
    exif[274] = 6
    source = BytesIO()
    photo.save(source, format="JPEG", exif=exif)
    reply = client.post("/api/batches", headers=headers, data={"name": "Mixed"}, files=[
        ("images", ("folder/oriented.jpg", source.getvalue(), "image/jpeg")),
        ("images", ("broken.png", b"invalid", "image/png")),
    ])
    assert reply.status_code == 200
    batch = reply.json()
    good, bad = batch["items"]
    assert good["filename"] == "oriented.jpg" and good["sequence"] == 1
    assert good["can_recognize"] and bad["status"] == "error" and not bad["can_recognize"]
    root = f"/api/batches/{batch['id']}/items"
    detail = client.get(f"{root}/{good['id']}").json()
    with Image.open(BytesIO(base64.b64decode(detail["image_url"].split(",")[1]))) as image:
        assert image.size == (1000, 2000)
        assert not image.getexif()
    assert client.get(f"{root}/{bad['id']}").json()["image_url"] is None
    assert client.post(f"{root}/{bad['id']}/recognize", headers=headers).status_code == 409


def test_bulk_confirmation_skips_open_manual_review(client):
    headers = login(client)
    batch = client.post("/api/demo", headers=headers).json()
    root = f"/api/batches/{batch['id']}"
    item = f"{root}/items/{batch['items'][0]['id']}"
    assert client.post(f"{item}/review", headers=headers).status_code == 200
    assert client.post(f"{root}/confirm-ready", headers=headers).json()["accepted"] == 0
    assert client.get(f"{root}/export.csv").status_code == 409


def test_same_image_cannot_be_recognized_concurrently_or_overwrite_raw(application, monkeypatch):
    original = MockProvider.recognize

    async def check():
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(self, image):
            started.set()
            await release.wait()
            return await original(self, image)

        monkeypatch.setattr(MockProvider, "recognize", slow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://test") as client:
            login_reply = await client.post("/api/login", json={"username": "test", "password": "test-pass-123"})
            headers = {"x-csrf-token": login_reply.json()["csrf"]}
            upload = await client.post("/api/batches", headers=headers, data={"name": "Parallel"},
                                       files={"images": ("a.jpg", picture(), "image/jpeg")})
            batch = upload.json()
            item = f"/api/batches/{batch['id']}/items/{batch['items'][0]['id']}"
            first = asyncio.create_task(client.post(f"{item}/recognize", headers=headers))
            await asyncio.wait_for(started.wait(), timeout=2)
            try:
                assert (await client.get(item)).json()["status"] == "processing"
                assert (await client.delete(f'/api/batches/{batch["id"]}', headers=headers)).status_code == 409
                assert (await client.post(f"{item}/recognize", headers=headers)).status_code == 409
            finally:
                release.set()
                assert (await first).status_code == 200
            raw = (await client.get(item)).json()["raw_text"]
            assert (await client.post(f"{item}/recognize", headers=headers)).status_code == 409
            assert (await client.get(item)).json()["raw_text"] == raw

    asyncio.run(check())


def test_expiry_and_app_restart_invalidate_session(application):
    store = application.state.workspaces
    store.now = lambda: 100.0
    with TestClient(application) as client:
        login(client)
        store.now = lambda: 100.0 + store.ttl_seconds + 1
        assert client.get("/api/batches").status_code == 401
        headers = login(client)
        assert client.post("/api/demo", headers=headers).status_code == 200
        token = client.cookies["fd_session"]
    with TestClient(application) as restarted:
        restarted.cookies.set("fd_session", token)
        assert restarted.get("/api/batches").status_code == 401


def test_live_quotas_charge_failed_calls_before_contacting_provider(monkeypatch):
    attempts = 0

    async def fail(self, image):
        nonlocal attempts
        attempts += 1
        raise ProviderError("simulated failure")

    monkeypatch.setattr(OpenRouterProvider, "recognize", fail)
    app = build_app(Settings(
        admin_password_hash=password_hash("admin-pass-123"),
        test_password_hash=password_hash("test-pass-123"),
        session_secret="x" * 32,
        model_provider="openrouter",
        openrouter_api_key="unused-test-key",
        openrouter_model="test-model",
        live_calls_per_session=25, live_calls_global=80,
    ))
    with TestClient(app) as client:
        for allowed in (25, 25, 25, 5):
            headers = login(client)
            upload = client.post("/api/batches", headers=headers, data={"name": "Quota"},
                                 files={"images": ("a.jpg", picture(), "image/jpeg")})
            batch = upload.json()
            endpoint = f"/api/batches/{batch['id']}/items/{batch['items'][0]['id']}/recognize"
            for _ in range(allowed):
                assert client.post(endpoint, headers=headers).status_code == 502
            assert client.post(endpoint, headers=headers).status_code == 429
        assert attempts == 80
