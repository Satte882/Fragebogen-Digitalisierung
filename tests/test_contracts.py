from __future__ import annotations

import csv
import io

import pytest
from pydantic import ValidationError

from app.contracts import Answer, FinalText, Recognition
from app.export import batch_csv, safe_cell
from app.providers import _json_from_message, MockProvider


def test_answer_values_and_status():
    assert Answer(value=1, status='answered').value == 1
    assert Answer(value=None, status='no_answer').value is None
    for data in ({'value': 0,'status':'answered'}, {'value':5,'status':'answered'},
                 {'value':2,'status':'multiple'}, {'value':True,'status':'answered'},
                 {'value':None,'status':'answered'}, {'value':1,'status':'no_answer'}):
        with pytest.raises(ValidationError):
            Answer.model_validate(data)


def test_text_consistency():
    FinalText.model_validate({'german_translation': '', 'text_status':'empty'})
    with pytest.raises(ValidationError):
        FinalText.model_validate({'german_translation': 'abc', 'text_status':'empty'})
    with pytest.raises(ValidationError):
        FinalText.model_validate({'german_translation': '', 'text_status':'translated'})


def test_mock_is_explicitly_not_a_model():
    import asyncio
    recognition, raw = asyncio.run(MockProvider().recognize(b'test'))
    assert recognition.recommended_status == 'review_required'
    assert 'DEMO-MODUS' in raw
    assert all(getattr(recognition, f'q{i}').value is None for i in range(1, 6))


def test_json_model_parsing():
    assert _json_from_message('```json\n{"q1": 1}\n```') == {'q1': 1}
    with pytest.raises((ValueError, __import__('json').JSONDecodeError)):
        _json_from_message('no json')
    with pytest.raises(ValueError, match='Duplicate'):
        _json_from_message('{"q1": {"value": 1, "value": 4}}')


def test_structured_findings_require_review_and_invalid_regions_are_ignored():
    data = {
        **{f"q{i}": {"value": 4, "status": "answered"} for i in range(1, 6)},
        "text": {"original_transcript": "", "source_language": "unknown",
                 "german_translation": "", "text_status": "empty"},
        "findings": [{"field": "q3", "kind": "unclear_mark", "reason": "Markierung unsicher."}],
        "regions": {"q3": [0.1, 0.2, 0.8, 0.3], "q4": [0.8, 0.2, 0.1, 0.3]},
    }
    result = Recognition.model_validate(data)
    assert result.recommended_status == "review_required"
    assert result.findings[0].field == "q3"
    assert result.regions == {"q3": [0.1, 0.2, 0.8, 0.3]}


def test_csv_injection_safety():
    for attack in ('=HYPERLINK("bad")', '+1+2', '-3+4', '@SUM(2)', '\t=SUM(1)', '\ttext', '\u00a0＝1'):
        assert safe_cell(attack).startswith("'")
    assert safe_cell('text').startswith('text')


def test_csv_only_final_no_raw_fields():
    batch = {'id':'batch-test', 'name':'Event A', 'items':{
        'i1':{'id':'i1','filename':'one.jpg','sequence':1,'status':'confirmed','review_mode':'corrected',
              'raw':{'secret':'SHOULD_NOT_EXPORT'},
              'final':{**{f'q{i}':{'value':None,'status':'no_answer'} for i in range(1,6)},
                       'text':{'german_translation':'=HYPERLINK("evil")','text_status':'translated'}}},
        'i2':{'id':'i2','filename':'two.jpg','sequence':2,'status':'review_required','review_mode':None,'final':None},
    }}
    output = batch_csv(batch).decode('utf-8-sig')
    assert 'SHOULD_NOT_EXPORT' not in output
    assert "'=HYPERLINK" in output
    values = list(csv.DictReader(io.StringIO(output), delimiter=';'))
    assert len(values) == 1
    assert values[0]['q2_value'] == ''
    assert values[0]['q2_status'] == 'no_answer'
    assert values[0]['review_mode'] == 'corrected'
