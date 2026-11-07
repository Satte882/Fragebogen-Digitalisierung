"""OpenRouter adapter contract tests without transmitting any images to the network."""
from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from app import providers
from app.providers import OpenRouterProvider, ProviderError


VALID_RESULT = {
    **{f'q{i}': {'value': (i % 4) + 1, 'status':'answered'} for i in range(1,6)},
    'text': {'original_transcript':'Hello there', 'source_language':'en',
             'german_translation':'Hallo', 'text_status':'translated'},
    'warnings': [],
}


def test_openrouter_multimodal_payload_and_result(monkeypatch):
    requests=[]
    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(VALID_RESULT)}}]})
    original_async_client=httpx.AsyncClient
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kw: original_async_client(transport=transport,**kw))
    recog,raw=asyncio.run(OpenRouterProvider('fake-test-key','google/gemini-test').recognize(b'synthetic-binary'))
    assert recog.recommended_status=='ready'
    assert recog.q1.value==2
    assert len(requests)==1
    request=requests[0]
    assert request.headers['authorization']=='Bearer fake-test-key'
    payload=json.loads(request.content)
    assert payload['model']=='google/gemini-test'
    assert payload['response_format']=={'type':'json_object'}
    parts=payload['messages'][0]['content']
    assert parts[0]['type']=='text' and 'TRAN' in parts[0]['text'].upper()
    assert parts[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert base64.b64decode(parts[1]['image_url']['url'].split(',')[1]) == b'synthetic-binary'
    assert 'Hello there' in raw


def test_openrouter_bad_json_is_safe_error(monkeypatch):
    original_async_client=httpx.AsyncClient
    transport=httpx.MockTransport(lambda req: httpx.Response(200,json={'choices':[{'message':{'content':'nonsense'}}]}))
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:original_async_client(transport=transport,**kw))
    with pytest.raises(ProviderError,match='Modellantwort'):
        asyncio.run(OpenRouterProvider('fake-test-key','google/gemini-test').recognize(b'synthetic-binary'))
