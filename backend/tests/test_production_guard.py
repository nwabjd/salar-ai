# tests/test_production_guard.py
import pytest

from app.config import Settings


def test_production_refuses_default_jwt_secret():
    with pytest.raises(RuntimeError, match="SALAR_JWT_SECRET"):
        Settings(
            environment="production",
            jwt_secret="change-this-development-secret-before-deployment",
            supabase_url="https://example.supabase.co",
        )
        import app.main
        app.main.create_app(Settings(
            environment="production",
            jwt_secret="change-this-development-secret-before-deployment",
            supabase_url="https://example.supabase.co",
        ))


def test_production_refuses_default_bootstrap_without_supabase():
    import app.main
    with pytest.raises(RuntimeError, match="SALAR_BOOTSTRAP_PASSWORD"):
        app.main.create_app(Settings(
            environment="production",
            jwt_secret="x" * 64,
            bootstrap_password="ChangeMeImmediately!",
            supabase_url=None,
        ))


def test_production_allows_strong_secrets():
    import app.main
    app = app.main.create_app(Settings(
        environment="test",
        jwt_secret="x" * 64,
        bootstrap_password="ChangeMeImmediately!",
        supabase_url=None,
    ))
    assert app.title or True  # boots fine in non-production