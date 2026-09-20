# backend/app/services/vault.py
import base64
import logging
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


class VaultError(Exception):
    pass


class Vault:
    """Fernet (AES-128-CBC + HMAC-SHA256) encryption for data at rest."""

    def __init__(self, master_key: Optional[str] = None) -> None:
        key = master_key or os.environ.get("SALAR_VAULT_KEY")
        if not key:
            # Fail closed in production: a known public key makes encryption
            # useless. In development the dev key keeps local flows working.
            if os.environ.get("SALAR_ENVIRONMENT", "development").lower() == "production":
                raise VaultError("SALAR_VAULT_KEY is required when SALAR_ENVIRONMENT=production")
            key = "default-dev-key-not-for-prod"
        encoded = key if isinstance(key, bytes) else key.encode()
        if len(encoded) != 44:
            encoded = base64.urlsafe_b64encode(encoded.ljust(32, b"0")[:32])
        self._fernet = Fernet(encoded)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise VaultError("invalid or tampered ciphertext") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def rotate(self, new_key: str, values: Dict[str, str]) -> Dict[str, str]:
        """Re-encrypt a set of {name: encrypted} values with a new master key."""
        decrypted = {name: self.decrypt(v) for name, v in values.items()}
        new_vault = Vault(new_key)
        return {name: new_vault.encrypt(p) for name, p in decrypted.items()}
