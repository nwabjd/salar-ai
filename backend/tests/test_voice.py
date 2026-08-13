# tests/test_voice.py
from app.database import Base, create_session_factory
from app.models import User, VoicePreferences
from app.services.voice import (
    PERSONALITIES, STYLE_PRESETS, VoiceService, normalize,
)


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'voice.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_normalize():
    assert normalize("Hey SALAR!") == "hey salar"


def test_styles_presets():
    assert "whisper" in STYLE_PRESETS
    assert "professional" in PERSONALITIES


def test_prefs_defaults(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        vs = VoiceService(db)
        prefs = vs.prefs_for("u1")
        assert prefs.wake_phrase == "hey salar"
        assert prefs.style == "neutral"
        assert prefs.wake_word_enabled is True
    engine.dispose()


def test_apply_style(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        vs = VoiceService(db)
        prefs = vs.prefs_for("u1")
        prefs.style = "whisper"
        params = vs.apply_style(prefs)
        assert params["style"] == "whisper"
        assert "-25%" in params["rate"]
    engine.dispose()


def test_wake_detect():
    vs = VoiceService(None)
    assert vs.wake_detect("hey salar what time is it") is True
    assert vs.wake_detect("hey salar!") is True
    assert vs.wake_detect("what is the weather") is False


def test_wake_matches_uses_prefs(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        vs = VoiceService(db)
        prefs = vs.prefs_for("u1")
        prefs.wake_phrase = "ok computer"
        assert vs.wake_matches("u1", "ok computer run report") is True
        assert vs.wake_matches("u1", "hey salar") is False
    engine.dispose()


def test_tts_params(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        vs = VoiceService(db)
        params = vs.tts_params("u1")
        assert params["voice"] == "en-US-AriaNeural"
        assert params["rate"]
        assert params["personality_prompt"]
    engine.dispose()


def test_preferences_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(VoicePreferences(id="vp1", user_id="u1", style="serious"))
        db.commit()
        assert db.get(VoicePreferences, "vp1").style == "serious"
    engine.dispose()
