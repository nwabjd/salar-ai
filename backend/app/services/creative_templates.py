# backend/app/services/creative_templates.py
import logging
import re
from typing import Any, Dict, List

log = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _safe_format(body: str, variables: Dict[str, str]) -> str:
    """Substitute {placeholder} vars, leaving any missing ones intact."""
    def repl(match):
        return variables.get(match.group(1), match.group(0))
    return _PLACEHOLDER.sub(repl, body)

TEMPLATES = {
    "email_outreach": {
        "name": "Email Outreach",
        "category": "email",
        "body": "Hi {name},\n\nI noticed {trigger}. I'd love to help you with {topic}.\n\nWould you be open to a quick chat?\n\nBest,\n{signature}",
    },
    "social_post": {
        "name": "Social Post",
        "category": "social",
        "body": "Big update: {headline}\n\n{body_text}\n\n# {hashtags}",
    },
    "meeting_agenda": {
        "name": "Meeting Agenda",
        "category": "meeting",
        "body": "# {title}\n\n1. {item_1}\n2. {item_2}\n3. {item_3}\n\nGoal: {goal}",
    },
    "weekly_summary": {
        "name": "Weekly Summary",
        "category": "report",
        "body": "## Week of {week_of}\n\nAccomplishments:\n- {accomplishment_1}\n- {accomplishment_2}\n\nNext week: {next_focus}",
    },
}


class CreativeTemplates:
    def list(self) -> List[Dict[str, Any]]:
        return [
            {"key": k, "name": v["name"], "category": v["category"], "body": v["body"]}
            for k, v in TEMPLATES.items()
        ]

    def render(self, template_key: str, variables: Dict[str, str]) -> Dict[str, Any]:
        template = TEMPLATES.get(template_key)
        if template is None:
            return {"status": "error", "detail": f"unknown template: {template_key}", "available": list(TEMPLATES.keys())}
        try:
            output = _safe_format(template["body"], variables)
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
        return {"status": "ok", "key": template_key, "name": template["name"], "output": output}
