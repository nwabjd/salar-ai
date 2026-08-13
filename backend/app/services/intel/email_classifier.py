# backend/app/services/intel/email_classifier.py
import logging
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)

CLASSIFICATION_RULES = [
    {"kind": "email_bill", "pattern": "invoice|bill|payment due|statement|receipt", "severity": "warning"},
    {"kind": "email_action", "pattern": "action required|please confirm|sign here|approve|respond by", "severity": "warning"},
    {"kind": "email_newsletter", "pattern": "unsubscribe|newsletter|weekly digest|issue #", "severity": "info"},
    {"kind": "email_notification", "pattern": "you have been mentioned|new comment|new follower|activity", "severity": "info"},
    {"kind": "email_important", "pattern": "urgent|important|security|account locked|verify your", "severity": "critical"},
    {"kind": "email_spam", "pattern": "lottery|winner|congratulations!|free gift|click here", "severity": "info"},
]


from .email_watch import classify_email as _base_classify


def classify_with_rules(subject: str, from_addr: str = "", body: str = "") -> Dict[str, Any]:
    kind, summary = _base_classify(subject, from_addr, body)
    matched = None
    severity = "info"
    import re
    hay = f"{subject} {from_addr} {body}".lower()
    for rule in CLASSIFICATION_RULES:
        if re.search(rule["pattern"], hay):
            matched = rule
            severity = rule["severity"]
            break
    return {"kind": kind, "summary": summary, "severity": severity, "matched_rule": matched}
