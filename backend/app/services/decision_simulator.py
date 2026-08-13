# backend/app/services/decision_simulator.py
import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_SIM_PROMPT = (
    "You are a decision simulator. Model the choice between the given options.\n"
    "Return ONLY a JSON object with this exact shape:\n"
    '{{"scenarios": [{{"option": "A", "assumptions": [...], "risks": [...], '
    '"likely_outcome": "short narrative", "probability_of_success": 0.7}}], '
    '"comparison": "2-3 sentence tradeoff analysis", "recommendation": "A" or "B" or "mixed"}}\n'
    "Question: {question}\nOptions: {options}"
)


class DecisionSimulatorError(Exception):
    pass


class DecisionSimulator:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    async def simulate(self, question: str, options: List[str]) -> Dict[str, Any]:
        if self._gemini is None:
            raise DecisionSimulatorError("Gemini client not configured")
        if len(options) < 2:
            raise DecisionSimulatorError("At least 2 options required")
        opts_text = "\n".join(f"- {o}" for o in options)
        messages = [{"role": "user", "content": _SIM_PROMPT.format(question=question, options=opts_text)}]
        text = await self._gemini.chat(messages)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = self._fallback(question, options, text)
        data["question"] = question
        data["options"] = options
        return data

    @staticmethod
    def _fallback(question: str, options: List[str], text: str) -> Dict[str, Any]:
        return {
            "scenarios": [
                {"option": o, "assumptions": [], "risks": ["unknown"], "likely_outcome": "Raw model response (unparsed).", "probability_of_success": 0.5}
                for o in options
            ],
            "comparison": text,
            "recommendation": "mixed",
        }
