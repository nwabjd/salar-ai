"""Email endpoints — list, search, read, send, delete via IMAP/SMTP."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..security import get_current_user
from ..models import User

router = APIRouter(prefix="/api/email", tags=["email"])

from ..services.state import email_accounts as _email_accounts


class EmailAccountConfig(BaseModel):
    address: str
    password: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = 993
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    use_ssl: bool = True


class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = None
    html: bool = False


class EmailSearchRequest(BaseModel):
    folder: str = "INBOX"
    query: str = "ALL"
    limit: int = 20


class EmailReadRequest(BaseModel):
    msg_id: str
    folder: str = "INBOX"


class EmailDeleteRequest(BaseModel):
    msg_id: str
    folder: str = "INBOX"


def _get_client(user_id: str):
    cfg = _email_accounts.get(user_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="No email account configured. Add one in Settings.")
    from ..services.email_client import EmailAccount
    return EmailAccount(**cfg)


def _get_client_safe(user_id: str):
    cfg = _email_accounts.get(user_id)
    if not cfg:
        return None
    from ..services.email_client import EmailAccount
    return EmailAccount(**cfg)


@router.post("/connect")
def connect_account(config: EmailAccountConfig, user=Depends(get_current_user)):
    _email_accounts[user.id] = config.model_dump()
    try:
        from ..services.email_client import EmailAccount
        client = EmailAccount(**config.model_dump())
        folders = client.get_folders_with_counts()
        return {"status": "connected", "address": config.address, "folders": folders}
    except Exception as e:
        _email_accounts.pop(user.id, None)
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")


@router.get("/status")
def email_status(user=Depends(get_current_user)):
    cfg = _email_accounts.get(user.id)
    if not cfg:
        return {"connected": False}
    return {"connected": True, "address": cfg["address"]}


@router.get("/folders")
def list_folders(user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        return {"folders": client.get_folders_with_counts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
def search_emails(req: EmailSearchRequest, user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        emails = client.search_emails(folder=req.folder, query=req.query, limit=req.limit)
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read")
def read_email(req: EmailReadRequest, user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        return client.read_email(msg_id=req.msg_id, folder=req.folder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send")
def send_email(req: EmailSendRequest, user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        return client.send_email(to=req.to, subject=req.subject, body=req.body, cc=req.cc, html=req.html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
def delete_email(req: EmailDeleteRequest, user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        return client.delete_email(msg_id=req.msg_id, folder=req.folder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread")
def unread_count(folder: str = "INBOX", user=Depends(get_current_user)):
    client = _get_client(user.id)
    try:
        return {"folder": folder, "unread": client.get_unread_count(folder)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
