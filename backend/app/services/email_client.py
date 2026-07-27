"""IMAP/SMTP email client — supports Gmail, Outlook, Yahoo, and any provider."""

import imaplib
import smtplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Any
import re
import json


IMAP_DEFAULTS = {
    "gmail.com": ("imap.gmail.com", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "live.com": ("outlook.office365.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "icloud.com": ("imap.mail.me.com", 993),
    "me.com": ("imap.mail.me.com", 993),
}

SMTP_DEFAULTS = {
    "gmail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp.office365.com", 587),
    "hotmail.com": ("smtp.office365.com", 587),
    "live.com": ("smtp.office365.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 587),
    "icloud.com": ("smtp.mail.me.com", 587),
    "me.com": ("smtp.mail.me.com", 587),
}


def _get_domain(email_address: str) -> str:
    return email_address.split("@")[-1].lower() if "@" in email_address else ""


def _decode_subject(subject: Optional[str]) -> str:
    if not subject:
        return "(no subject)"
    decoded_parts = decode_header(subject)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result) or "(no subject)"


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    text = re.sub(r"<[^>]+>", " ", html)
                    return re.sub(r"\s+", " ", text).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


class EmailAccount:
    def __init__(self, address: str, password: str, imap_host: str = None, imap_port: int = 993,
                 smtp_host: str = None, smtp_port: int = 587, use_ssl: bool = True):
        self.address = address
        self.password = password
        domain = _get_domain(address)

        self.imap_host = imap_host or IMAP_DEFAULTS.get(domain, (f"imap.{domain}", 993))[0]
        self.imap_port = imap_port or IMAP_DEFAULTS.get(domain, (None, 993))[1]
        self.smtp_host = smtp_host or SMTP_DEFAULTS.get(domain, (f"smtp.{domain}", 587))[0]
        self.smtp_port = smtp_port or SMTP_DEFAULTS.get(domain, (None, 587))[1]
        self.use_ssl = use_ssl

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        mail.login(self.address, self.password)
        return mail

    def _connect_smtp(self) -> smtplib.SMTP:
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.ehlo()
        if self.use_ssl:
            server.starttls()
            server.ehlo()
        server.login(self.address, self.password)
        return server

    def list_folders(self) -> List[str]:
        mail = self._connect_imap()
        try:
            status, folders = mail.list()
            result = []
            for f in folders:
                if isinstance(f, bytes):
                    name = f.decode().split('" "')[-1].rstrip('"')
                    result.append(name)
            return result
        finally:
            mail.logout()

    def search_emails(self, folder: str = "INBOX", query: str = "ALL", limit: int = 20) -> List[Dict[str, Any]]:
        mail = self._connect_imap()
        try:
            mail.select(folder)
            status, data = mail.search(None, query)
            if status != "OK":
                return []
            msg_ids = data[0].split()
            if not msg_ids:
                return []

            msg_ids = msg_ids[-limit:]
            msg_ids.reverse()

            results = []
            for mid in msg_ids:
                status, msg_data = mail.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
                if status != "OK":
                    continue
                header_data = msg_data[0][1]
                msg = email_lib.message_from_bytes(header_data)
                results.append({
                    "id": mid.decode(),
                    "from": msg.get("From", ""),
                    "to": msg.get("To", ""),
                    "subject": _decode_subject(msg.get("Subject")),
                    "date": msg.get("Date", ""),
                })
            return results
        finally:
            mail.logout()

    def read_email(self, msg_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        mail = self._connect_imap()
        try:
            mail.select(folder)
            status, msg_data = mail.fetch(msg_id.encode() if isinstance(msg_id, str) else msg_id, "(RFC822)")
            if status != "OK":
                return {"error": "Message not found"}
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)
            return {
                "id": msg_id,
                "from": msg.get("From", ""),
                "to": msg.get("To", ""),
                "cc": msg.get("Cc", ""),
                "subject": _decode_subject(msg.get("Subject")),
                "date": msg.get("Date", ""),
                "body": _extract_body(msg)[:10000],
                "is_reply": bool(msg.get("In-Reply-To")),
            }
        finally:
            mail.logout()

    def send_email(self, to: str, subject: str, body: str, cc: str = None, html: bool = False) -> Dict[str, Any]:
        msg = MIMEMultipart("alternative" if html else "plain")
        msg["From"] = self.address
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = subject

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        server = self._connect_smtp()
        try:
            recipients = [to]
            if cc:
                recipients.extend(cc.split(","))
            server.sendmail(self.address, recipients, msg.as_string())
            return {"status": "sent", "to": to, "subject": subject}
        finally:
            server.quit()

    def delete_email(self, msg_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        mail = self._connect_imap()
        try:
            mail.select(folder)
            mail.store(msg_id.encode() if isinstance(msg_id, str) else msg_id, "+FLAGS", "\\Deleted")
            mail.expunge()
            return {"status": "deleted", "id": msg_id}
        finally:
            mail.logout()

    def mark_as_read(self, msg_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        mail = self._connect_imap()
        try:
            mail.select(folder)
            mail.store(msg_id.encode() if isinstance(msg_id, str) else msg_id, "+FLAGS", "\\Seen")
            return {"status": "marked_read", "id": msg_id}
        finally:
            mail.logout()

    def get_unread_count(self, folder: str = "INBOX") -> int:
        mail = self._connect_imap()
        try:
            mail.select(folder)
            status, data = mail.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                return len(data[0].split())
            return 0
        finally:
            mail.logout()

    def get_folders_with_counts(self) -> List[Dict[str, Any]]:
        mail = self._connect_imap()
        try:
            status, folders = mail.list()
            result = []
            for f in folders:
                if isinstance(f, bytes):
                    parts = f.decode().split('" "')[-1].rstrip('"')
                    name = parts
                    try:
                        mail.select(name)
                        status, all_data = mail.search(None, "ALL")
                        total = len(all_data[0].split()) if status == "OK" and all_data[0] else 0
                        status, unread_data = mail.search(None, "UNSEEN")
                        unread = len(unread_data[0].split()) if status == "OK" and unread_data[0] else 0
                        result.append({"folder": name, "total": total, "unread": unread})
                    except Exception:
                        result.append({"folder": name, "total": 0, "unread": 0})
            return result
        finally:
            mail.logout()
