# tests/test_phase8.py
import pytest

from app.database import Base, create_session_factory
from app.models import ActionLog, Memory, User
from app.services.consent import CONSENT_CATEGORIES, ConsentManager
from app.services.vault import Vault, VaultError
from app.services.privacy_scanner import PrivacyScanner
from app.services.local_ai import LocalAIMode


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p8.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_consent_categories():
    assert {"voice", "camera", "screen", "emails"} <= set(CONSENT_CATEGORIES)


def test_consent_set_and_granted(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        cm = ConsentManager(db)
        cm.set("u1", "voice", True)
        db.commit()
        assert cm.granted("u1", "voice") is True
        cm.set("u1", "voice", False)
        db.commit()
        assert cm.granted("u1", "voice") is False
        assert cm.granted("u1", "camera") is False
    engine.dispose()


def test_consent_invalid_category(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        with pytest.raises(ValueError):
            ConsentManager(db).set("u1", "brainwaves", True)
    engine.dispose()


def test_consent_snapshot(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        cm = ConsentManager(db)
        cm.set("u1", "voice", True)
        snap = cm.snapshot("u1")
        assert len(snap) == len(CONSENT_CATEGORIES)
        by_cat = {s["category"]: s for s in snap}
        assert by_cat["voice"]["granted"] is True
        assert by_cat["screen"]["granted"] is False
    engine.dispose()


def test_vault_roundtrip():
    key = Vault.generate_key()
    v = Vault(key)
    token = v.encrypt("top secret data")
    assert v.decrypt(token) == "top secret data"


def test_vault_tamper_detected():
    v = Vault()
    token = v.encrypt("hello")
    with pytest.raises(VaultError):
        v.decrypt(token[:-4] + "xxxx")


def test_vault_rotate():
    old = Vault.generate_key()
    new = Vault.generate_key()
    v = Vault(old)
    values = {"db_password": v.encrypt("p@ss"), "api_key": v.encrypt("k12345")}
    rotated = Vault(old).rotate(new, values)
    v2 = Vault(new)
    assert v2.decrypt(rotated["db_password"]) == "p@ss"
    assert v2.decrypt(rotated["api_key"]) == "k12345"


def test_privacy_scanner_detects_secret(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="credentials", content="password = hunter2superlong"))
        db.commit()
        report = PrivacyScanner(db).scan_report("u1")
        assert report["total"] >= 1
        assert report["critical"] >= 1
    engine.dispose()


def test_privacy_scanner_clean(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="grocery list", content="milk eggs bread"))
        db.commit()
        report = PrivacyScanner(db).scan_report("u1")
        assert report["total"] == 0
    engine.dispose()


def test_local_ai_prefs_defaults(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        p = LocalAIMode(db).prefs_for("u1")
        assert p.local_ai_mode is False
        assert p.data_retention_days == 30
    engine.dispose()


def test_local_ai_update_and_evaluate(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        lai = LocalAIMode(db)
        lai.update("u1", local_ai_mode=True, data_retention_days=7)
        db.commit()
        p = lai.prefs_for("u1")
        assert p.local_ai_mode is True
        assert p.data_retention_days == 7
        ev = lai.evaluate("u1", "stt")
        assert ev["location"] == "local"
        assert ev["local_ai_mode"] is True
    engine.dispose()
