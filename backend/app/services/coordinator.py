from typing import Iterable

import httpx

from .ollama import OllamaClient


class AICoordinator:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def reply(self, *, prompt: str, messages: Iterable, memories: Iterable, documents: Iterable) -> str:
        context_parts = []
        memory_text = "\n".join(f"- {item.title}: {item.content}" for item in memories)
        if memory_text:
            context_parts.append(f"Relevant saved memory:\n{memory_text}")
        document_text = "\n".join(f"- {item.filename}: {item.extracted_text[:800]}" for item in documents)
        if document_text:
            context_parts.append(f"Relevant documents:\n{document_text}")
        system = (
            "You are SALAR, a concise private AI assistant. Keep user data private, explain risky actions, "
            "and never claim a computer action happened unless a device result confirms it."
        )
        if context_parts:
            system += "\n\n" + "\n\n".join(context_parts)
        payload = [{"role": "system", "content": system}]
        payload.extend({"role": item.role, "content": item.content} for item in list(messages)[-16:])
        payload.append({"role": "user", "content": prompt})
        try:
            return await self.ollama.chat(payload)
        except (httpx.HTTPError, KeyError, OSError):
            return (
                "The configured AI model is currently unavailable. Your message was saved, and SALAR will "
                "respond normally when the backend can reach Ollama."
            )

