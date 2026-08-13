# backend/app/api/vault.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.vault import Vault, VaultError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vault", tags=["vault"])


class EncryptRequest(BaseModel):
    plaintext: str


class DecryptRequest(BaseModel):
    token: str


@router.post("/encrypt")
def encrypt_value(
    body: EncryptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"token": Vault().encrypt(body.plaintext)}


@router.post("/decrypt")
def decrypt_value(
    body: DecryptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return {"plaintext": Vault().decrypt(body.token)}
    except VaultError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
