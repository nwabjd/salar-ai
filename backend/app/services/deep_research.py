# backend/app/services/deep_research.py
import json
import logging
from typing import Any, Dict, List, Optional

from ..models import DeepResearch, token_id, utcnow

log = logging.getLogger(__name__)

_PERSPECTIVES = [
    "You are an independent research agent. Give a thorough, objective analysis based on verifiable facts.",
    "You are a skeptical research agent. Challenge assumptions, demand sources, and flag anything questionable.",
    "You are a complementary research agent. Fill gaps the other researchers might miss; add practical examples.",
]

_SYNTHESIS_PROMPT = (
    "You are a research synthesizer. You have received findings from 3 independent researchers on the same question.\n"
    "Compare their claims. Flag contradictions clearly. Identify consensus points and unresolved questions.\n"
    "Return a JSON object with this shape:\n"
    '{{"synthesis": "verified summary", "confidence": "high|medium|low", '
    '"consensus_points": [...], "contradictions": [...], "unresolved": [...], '
    '"sources_cited": [...]}}\n\n'
    "Findings:\n{findings}\n\n"
    "Original question: {goal}"
)


class DeepResearchError(Exception):
    pass


class DeepResearchMode:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    async def run(self, goal: str, *, num_agents: int = 3) -> Dict[str, Any]:
        if self._gemini is None:
            raise DeepResearchError("Gemini client not configured")
        perspectives = _PERSPECTIVES[:num_agents]
        findings: List[Dict[str, str]] = []
        for i, prompt in enumerate(perspectives):
            messages = [
                {"role": "user", "content": f"{prompt}\n\nQuestion: {goal}"}
            ]
            text = await self._gemini.chat(messages)
            findings.append({"agent_id": i, "perspective": prompt[:50], "content": text})

        findings_text = "\n\n".join(
            f"Agent {f['agent_id']} ({f['perspective']}...):\n{f['content']}"
            for f in findings
        )
        synth_messages = [{"role": "user", "content": _SYNTHESIS_PROMPT.format(findings=findings_text, goal=goal)}]
        synth_text = await self._gemini.chat(synth_messages)

        synthesis = {}
        try:
            synthesis = json.loads(synth_text)
        except json.JSONDecodeError:
            synthesis = {"synthesis": synth_text, "confidence": "medium", "consensus_points": [], "contradictions": [], "unresolved": [], "sources_cited": []}

        return {
            "goal": goal,
            "num_agents": num_agents,
            "findings": findings,
            "synthesis": synthesis,
        }


    def store(self, db, user_id: str, result: Dict[str, Any]) -> DeepResearch:
        row = DeepResearch(
            id=token_id(), user_id=user_id, goal=result["goal"],
            agents_json=json.dumps(result["findings"]),
            synthesis_json=json.dumps(result["synthesis"]),
            findings_json=json.dumps(result.get("findings", [])),
            status="completed", created_at=utcnow(),
        )
        db.add(row)
        db.commit()
        return row
