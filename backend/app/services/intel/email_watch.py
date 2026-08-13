"""Email watch — scans a user's inbox in the background and turns notable unseen
mail into intel ledger events.

Classification is deliberately conservative: anything that looks like a bill,
payment, action request, or important sender becomes a warning event; everything
else becomes an info event with a low severity. The email client is blocking
IMAP, so callers run this in a worker thread.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import IntelEmailSeen
from ..email_client import EmailAccount
from ..jobs.store import utcnow
from .events import IntelEventStore

log = logging.getLogger(__name__)

# Classification patterns — matched against the normalized subject line.
_BILL_WORDS = [
    r"invoice", r"bill(?!s?)", r"receipt", r"payment", r"subscription",
    r"renewal", r"statement", r"charge", r"you owe", r"past due", r"overdue",
    r"autopay", r"auto-?pay", r"billing", r"due date", r"your order",
]
_ACTION_WORDS = [
    r"action required", r"please review", r"approval", r"need your", r"response needed",
    r"sign here", r"please respond", r"confirm", r"follow[- ]?up", r"urgent",
    r"important", r"final notice", r"deadline", r"appointment", r"reminder",
]
_IMPORTANT_SENDER = [
    r"@law", r"@legal", r"@finance", r"@accounting", r"@tax", r"attorney",
    r"lawyer", r"court", r"bank", r"irs", r"tax", r"payroll", r"insurance",
]

_BILL_RE = re.compile(r"(?:%s)" % "|".join(_BILL_WORDS), re.IGNORECASE)
_ACTION_RE = re.compile(r"(?:%s)" % "|".join(_ACTION_WORDS), re.IGNORECASE)
_IMPORTANT_SENDER_RE = re.compile(r"(?:%s)" % "|".join(_IMPORTANT_SENDER), re.IGNORECASE)
_NEWSLETTER_RE = re.compile(r"(newsletter|unsubscribe|weekly digest|daily digest)", re.IGNORECASE)


def classify_email(subject: str, from_addr: str = "", body: str = "") -> Tuple[str, str]:
    """Return (kind, severity) for an email.

    Order matters: bills beat newsletters, action requests beat everything except
    bills, and important senders get a warning when nothing more specific matched.
    """
    text = f"{subject} {body}".strip()[:2000]
    from_low = (from_addr or "").lower()

    if _NEWSLETTER_RE.search(text):
        return "email_info", "info"

    if _BILL_RE.search(text):
        return "email_bill", "warning"

    if _ACTION_RE.search(text):
        return "email_action", "warning"

    if _IMPORTANT_SENDER_RE.search(from_low):
        return "email_important", "warning"

    return "email_info", "info"


def scan_email_account(
    db: Session,
    user_id: str,
    cfg: Dict[str, Any],
    *,
    folder: str = "INBOX",
    limit: int = 50,
    mark_events_read: bool = False,
) -> Dict[str, Any]:
    """Scan one inbox and record events for previously-unseen messages.

    Returns a summary dict for the job output. Raises on connection failure so the
    worker retries; per-message errors are tolerated and recorded.
    """
    store = IntelEventStore(db)
    account = EmailAccount(**cfg)

    results: Dict[str, Any] = {"scanned": 0, "new_events": 0, "errors": 0, "folder": folder}

    unseen = account.search_emails(folder=folder, query="UNSEEN", limit=limit)
    results["scanned"] = len(unseen)

    for item in unseen:
        msg_id = str(item.get("id") or "")
        if not msg_id:
            continue
        if _already_seen(db, user_id, folder, msg_id):
            continue

        try:
            subject = item.get("subject") or "(no subject)"
            from_addr = item.get("from") or ""
            kind, severity = classify_email(subject, from_addr)
            if kind == "email_info":
                # Quiet info mail — mark seen, don't create a ledger event.
                _mark_seen(db, user_id, folder, msg_id)
                results["skipped_info"] = results.get("skipped_info", 0) + 1
                continue

            body = ""
            try:
                detail = account.read_email(msg_id, folder=folder)
                body = detail.get("body") or ""
                kind, severity = classify_email(subject, from_addr, body)
            except Exception:
                log.debug("Could not fetch body for message %s", msg_id, exc_info=True)

            store.record(
                user_id=user_id,
                kind=kind,
                severity=severity,
                source="email",
                title=subject,
                summary=body[:600] or subject,
                detail={
                    "from": from_addr,
                    "date": item.get("date") or "",
                    "message_id": msg_id,
                    "folder": folder,
                },
                evidence=[{"type": "email", "message_id": msg_id, "folder": folder, "subject": subject, "from": from_addr}],
            )
            _mark_seen(db, user_id, folder, msg_id)
            results["new_events"] += 1
        except Exception as exc:
            log.warning("Email watch error on message %s: %s", msg_id, exc)
            _mark_seen(db, user_id, folder, msg_id)
            results["errors"] += 1

    db.commit()
    return results


def _already_seen(db: Session, user_id: str, folder: str, message_uid: str) -> bool:
    row = db.scalar(
        select(IntelEmailSeen.id).where(
            IntelEmailSeen.user_id == user_id,
            IntelEmailSeen.folder == folder,
            IntelEmailSeen.message_uid == message_uid,
        )
    )
    return row is not None


def _mark_seen(db: Session, user_id: str, folder: str, message_uid: str) -> None:
    db.add(IntelEmailSeen(user_id=user_id, folder=folder, message_uid=message_uid, seen_at=utcnow()))
