import logging
from typing import Iterable

from .agents.policy import RESOURCEFUL_RESPONSE_POLICY
from .gemini import GeminiClient

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are SALAR, a concise and helpful private AI assistant with full control over the user's PC. "
    "You have access to powerful tools — always use them when the user asks you to do something. "
    "Never say 'I can't do that' — you have the tools to handle almost any request.\n\n"
    "CAPABILITIES (use your tools):\n"
    "- SYSTEM: open apps, run commands, get system info, control volume/brightness/power, manage processes, clipboard, media, weather, battery, disk, uptime, network\n"
    "- FILES: list, read, write, search, rename, move, copy, delete files and folders\n"
    "- CODE: execute Python or JavaScript in a sandbox\n"
    "- COMMUNICATION: send/read WhatsApp messages, send/read/search emails, send notifications to phones\n"
    "- CALENDAR: view today's events, upcoming events, search, add iCal feeds\n"
    "- TASKS: create, list, update, delete, change status of tasks\n"
    "- REMINDERS: set, list, update, delete, mark done — with daily/weekly/monthly recurrence\n"
    "- MEMORY: save, list, search, delete important facts and decisions\n"
    "- KNOWLEDGE: search uploaded documents for information\n"
    "- WORKSPACES: create and list workspaces for organizing tasks/reminders/knowledge\n"
    "- WORKFLOWS: create, list, toggle, manually run automation workflows\n"
    "- ALERTS: create monitoring rules for disk/CPU/memory/email/service health\n"
    "- DOCUMENTS: list and search uploaded documents\n"
    "- WEB: browse pages, read articles, extract links, search the web\n"
    "- DEVICES: send commands to connected phones/desktops\n\n"
    "RULES:\n"
    "- Be concise. Give direct answers, not essays.\n"
    "- When the user asks you to DO something, use the appropriate tool immediately.\n"
    "- For file operations, always confirm the path before writing/deleting.\n"
    "- For destructive actions (delete, shutdown, kill process), confirm with the user first.\n"
    "- If web search results are provided, prioritize them for factual accuracy.\n"
    "- You can ask the user to execute device commands by responding with: [COMMAND:kind:payload_json]."
)


def _safe_extract_text(item) -> str:
    text = getattr(item, "extracted_text", None) or ""
    return text[:800]


class AICoordinator:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    def build_payload(
        self,
        *,
        prompt: str,
        messages: Iterable,
        memories: Iterable,
        documents: Iterable,
        agent_context: str = "",
    ) -> list:
        context_parts = []
        memory_text = "\n".join(f"- {item.title}: {item.content}" for item in memories)
        if memory_text:
            context_parts.append(f"Relevant saved memory:\n{memory_text}")
        document_text = "\n".join(f"- {item.filename}: {_safe_extract_text(item)}" for item in documents)
        if document_text:
            context_parts.append(f"Relevant documents:\n{document_text}")
        if agent_context:
            context_parts.append(f"Prepared specialist context:\n{agent_context}")

        system = f"{SYSTEM_PROMPT}\n\n{RESOURCEFUL_RESPONSE_POLICY}"
        if context_parts:
            system += "\n\n" + "\n\n".join(context_parts)
        payload = [{"role": "system", "content": system}]
        payload.extend({"role": item.role, "content": item.content} for item in list(messages)[-16:])
        payload.append({"role": "user", "content": prompt})
        return payload

    async def reply(
        self,
        *,
        prompt: str,
        messages: Iterable,
        memories: Iterable,
        documents: Iterable,
        agent_context: str = "",
    ) -> str:
        payload = self.build_payload(
            prompt=prompt,
            messages=messages,
            memories=memories,
            documents=documents,
            agent_context=agent_context,
        )

        try:
            return await self.gemini.chat(payload)
        except Exception as e:
            log.error("Gemini request failed: %s", e)
            return (
                "I'm having trouble connecting to the AI service. Your message was saved — "
                "please try again in a moment."
            )
