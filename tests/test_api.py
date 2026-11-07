from __future__ import annotations

from io import BytesIO
import csv
import io
import json
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
    batchid=batch['id']; imageid=batch['items'][0]['id']
    detail=client.get(f'/api/batches/{batchid}/items/{imageid}').json()
    assert detail['raw']['q1']['value']==4
    assert detail['raw']['text']['german_translation']=='Alles war gut organisiert.'
    assert detail['source']=='synthetic_demo'
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
    assert client.post(endpoint+'/confirm',headers=head,json=payload).status_code==409
    assert client.post(endpoint+'/review',headers=head).status_code==200
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


def test_same_login_isolation(application):
    with TestClient(application) as first, TestClient(application) as second:
        first_headers=login(first,'test')
        second_headers=login(second,'test')
        one=first.post('/api/demo',headers=first_headers).json()
        bid=one['id']; iid=one['items'][0]['id']
        assert second.get('/api/batches').json()==[]
        assert second.get(f'/api/batches/{bid}').status_code==404
        assert second.get(f'/api/batches/{bid}/items/{iid}').status_code==404
        assert second.post(f'/api/batches/{bid}/confirm-ready',headers=second_headers).status_code==404
        assert second.get(f'/api/batches/{bid}/export.csv').status_code==404
        assert first.get(f'/api/batches/{bid}/items/{iid}').status_code==200


def test_cross_site_cookie_csrf_and_invalid_confirmation(client):
    head=login(client)
    batch=client.post('/api/demo',headers=head).json();bid=batch['id'];iid=batch['items'][0]['id']
    route=f'/api/batches/{bid}/items/{iid}'
    assert client.post(route+'/review',headers={'x-csrf-token':'invalid'}).status_code==403
    raw=client.get(route).json()['raw']
    invalid=q_payload(raw);invalid['q1']={'value':5,'status':'answered'}
    assert client.post(route+'/confirm',headers=head,json=invalid).status_code==422
    invalid=q_payload(raw);invalid['text']={'german_translation':'made up','text_status':'empty'}
    assert client.post(route+'/confirm',headers=head,json=invalid).status_code==422
