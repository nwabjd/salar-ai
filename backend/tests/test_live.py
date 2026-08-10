import jwt
import pytest
from fastapi import HTTPException

from app.api.live import _translate_provider_event
from app.config import Settings
from app.security import decode_backend_token
from app.services.gemini_live import build_setup


def test_live_settings_use_server_side_gemini_configuration():
    settings = Settings(
        gemini_api_key='server-secret',
        gemini_live_model='gemini-3.1-flash-live-preview',
    )
    assert settings.gemini_api_key == 'server-secret'
    assert settings.gemini_live_model == 'gemini-3.1-flash-live-preview'


def test_live_setup_uses_configured_gemini_model():
    message = build_setup('gemini-3.1-flash-live-preview', 'Kore')
    assert message['setup']['model'] == 'models/gemini-3.1-flash-live-preview'
    assert 'OpenAI-Beta' not in str(message)


def test_retryable_gemini_error_is_sanitized_for_browser():
    assert _translate_provider_event({
        'error': {
            'code': 503,
            'status': 'UNAVAILABLE',
            'message': 'private upstream detail',
        }
    }) == [{'type': 'provider_retry', 'error': 'Live voice is reconnecting'}]


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ({'setupComplete': {}}, [{'type': 'ready'}]),
        ({'serverContent': {'interrupted': True}}, [{'type': 'interrupted'}]),
        ({'serverContent': {'generationComplete': True}}, [{'type': 'response_done'}]),
    ],
)
def test_gemini_events_are_translated_to_stable_browser_events(source, expected):
    assert _translate_provider_event(source) == expected


def test_backend_token_decoder_rejects_expired_or_invalid_tokens():
    with pytest.raises(HTTPException) as exc:
        decode_backend_token('not-a-token', 'secret')
    assert exc.value.status_code == 401

    expired = jwt.encode({'sub': 'user-1', 'exp': 1}, 'secret', algorithm='HS256')
    with pytest.raises(HTTPException) as exc:
        decode_backend_token(expired, 'secret')
    assert exc.value.status_code == 401
