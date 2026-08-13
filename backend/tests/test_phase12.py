# tests/test_phase12.py
import pytest

from app.database import Base, create_session_factory
from app.models import MediaMemory, User, WidgetPrefs
from app.services.image_gen import ImageGenerator
from app.services.media_memory import MediaMemoryStore
from app.services.creative_templates import CreativeTemplates
from app.services.presentation import PresentationBuilder
from app.services.widgets import WidgetService, WIDGET_DEFINITIONS
from app.services.ar_status import ARStatus
from app.services.wallpapers import WallpaperManager


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p12.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


@pytest.mark.asyncio
async def test_image_gen_no_key():
    r = await ImageGenerator(api_key=None).generate("a cat")
    assert r["status"] == "unavailable"


@pytest.mark.asyncio
async def test_image_gen_bad_key():
    r = await ImageGenerator(api_key="not-a-real-key").generate("a cat")
    # should not raise; returns error
    assert r["status"] in ("error", "unavailable")


def test_media_memory_record_list_delete(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ms = MediaMemoryStore(db)
        ms.record("u1", "image", caption="my screen")
        ms.record("u1", "audio", transcript="hello")
        db.commit()
        assert len(ms.list("u1")) == 2
        assert len(ms.list("u1", kind="image")) == 1
        mid = ms.list("u1", kind="audio")[0]["id"]
        assert ms.delete("u1", mid) is True
        db.commit()
        assert len(ms.list("u1")) == 1
    engine.dispose()


def test_media_memory_invalid_kind(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        with pytest.raises(ValueError):
            MediaMemoryStore(db).record("u1", "hologram")
    engine.dispose()


def test_creative_templates_list():
    tl = CreativeTemplates()
    keys = {t["key"] for t in tl.list()}
    assert "email_outreach" in keys


def test_creative_template_render():
    tl = CreativeTemplates()
    r = tl.render("email_outreach", {"name": "Alice", "trigger": "your website", "topic": "marketing", "signature": "SALAR"})
    assert r["status"] == "ok"
    assert "Hi Alice" in r["output"]
    assert "marketing" in r["output"]


def test_creative_template_unknown():
    r = CreativeTemplates().render("nope", {})
    assert r["status"] == "error"


def test_presentation_build_html():
    pb = PresentationBuilder()
    html = pb.build_html("Deck", [{"title": "Intro", "body": ["point one", "point two"]}])
    assert "<html" in html
    assert "Intro" in html
    assert "<li>point one</li>" in html


def test_presentation_outline():
    pb = PresentationBuilder()
    outline = pb.outline(["A", "B"])
    assert len(outline) == 2
    assert outline[0]["title"] == "A"


def test_widget_definitions():
    assert any(w["key"] == "missions" for w in WIDGET_DEFINITIONS)


def test_widget_save_get(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ws = WidgetService(db)
        ws.save("u1", ["missions", "tasks"])
        db.commit()
        assert ws.get("u1") == ["missions", "tasks"]
    engine.dispose()


def test_widget_defaults(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ws = WidgetService(db)
        assert len(ws.get("u1")) >= 1
    engine.dispose()


def test_ar_status():
    s = ARStatus().check()
    assert s["status"] == "ok"
    assert "gltf" in s["formats"]


def test_wallpaper_save_list(tmp_path):
    wm = WallpaperManager(tmp_path)
    r = wm.save(b"\x89PNGfake", name="sunset")
    assert r["status"] == "ok"
    assert r["filename"].startswith("sunset_")
    assert len(wm.list()) == 1


def test_wallpaper_list_empty(tmp_path):
    assert WallpaperManager(tmp_path / "nope").list() == []


def test_media_memory_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(MediaMemory(id="mm1", user_id="u1", kind="video"))
        db.commit()
        assert db.get(MediaMemory, "mm1").kind == "video"
    engine.dispose()
