import jwt
import pytest
from fastapi import HTTPException

from app.api.live import (
    _build_session_update,
    _openai_headers,
    _openai_realtime_url,
    _translate_openai_event,
)
from app.config import Settings
from app.security import decode_backend_token


def test_realtime_settings_are_server_side():
    settings = Settings(openai_api_key='server-secret', openai_realtime_model='gpt-realtime')
    assert settings.openai_api_key == 'server-secret'
    assert settings.openai_realtime_model == 'gpt-realtime'


def test_session_update_uses_native_audio_semantic_vad_and_noise_reduction():
    message = _build_session_update('gpt-realtime', 'marin')
    session = message['session']
    assert session['output_modalities'] == ['audio']
    assert session['audio']['input']['format'] == {'type': 'audio/pcm', 'rate': 24000}
    assert session['audio']['input']['noise_reduction'] == {'type': 'far_field'}
    assert session['audio']['input']['turn_detection'] == {
        'type': 'semantic_vad',
        'eagerness': 'low',
        'create_response': True,
        'interrupt_response': True,
    }
    assert session['audio']['output']['voice'] == 'marin'
    assert 'model' not in session


def test_ga_realtime_connection_does_not_request_retired_beta_shape():
    assert _openai_realtime_url('gpt-realtime') == (
        'wss://api.openai.com/v1/realtime?model=gpt-realtime'
    )
    assert _openai_headers('server-secret') == {
        'Authorization': 'Bearer server-secret',
    }


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ({'type': 'input_audio_buffer.speech_started'}, {'type': 'speech_started'}),
        ({'type': 'input_audio_buffer.speech_stopped'}, {'type': 'speech_stopped'}),
        ({'type': 'response.output_audio.delta', 'delta': 'AAA='}, {'type': 'audio', 'data': 'AAA='}),
        ({'type': 'response.output_audio_transcript.delta', 'delta': 'Hello'}, {'type': 'output_transcript_delta', 'text': 'Hello'}),
        ({'type': 'conversation.item.input_audio_transcription.completed', 'transcript': 'Hi'}, {'type': 'input_transcript_completed', 'text': 'Hi'}),
        ({'type': 'response.done'}, {'type': 'response_done'}),
    ],
)
def test_openai_events_are_translated_to_stable_browser_events(source, expected):
    assert _translate_openai_event(source) == expected


def test_backend_token_decoder_rejects_expired_or_invalid_tokens():
    with pytest.raises(HTTPException) as exc:
        decode_backend_token('not-a-token', 'secret')
    assert exc.value.status_code == 401

    expired = jwt.encode({'sub': 'user-1', 'exp': 1}, 'secret', algorithm='HS256')
    with pytest.raises(HTTPException) as exc:
        decode_backend_token(expired, 'secret')
    assert exc.value.status_code == 401
