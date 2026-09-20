# backend/tests/test_vault_guard.py
"""Vault fails closed in production: no default key when SALAR_VAULT_KEY is unset."""
import pytest

from app.services.vault import Vault, VaultError


def test_vault_requires_key_in_production(monkeypatch):
    monkeypatch.delenv("SALAR_VAULT_KEY", raising=False)
    monkeypatch.setenv("SALAR_ENVIRONMENT", "production")
    with pytest.raises(VaultError):
        Vault()


def test_vault_accepts_explicit_key_in_production(monkeypatch):
    monkeypatch.setenv("SALAR_ENVIRONMENT", "production")
    vault = Vault(master_key="k" * 32)
    token = vault.encrypt("secret")
    assert vault.decrypt(token) == "secret"


def test_vault_env_key_is_used(monkeypatch):
    monkeypatch.setenv("SALAR_VAULT_KEY", "e" * 32)
    monkeypatch.setenv("SALAR_ENVIRONMENT", "production")
    vault = Vault()
    assert vault.decrypt(vault.encrypt("round-trip")) == "round-trip"


def test_vault_dev_default_still_round_trips(monkeypatch):
    monkeypatch.delenv("SALAR_VAULT_KEY", raising=False)
    monkeypatch.setenv("SALAR_ENVIRONMENT", "development")
    vault = Vault()
    assert vault.decrypt(vault.encrypt("x")) == "x"