"""
SALAAR — NIM intelligence + specialized benchmarks (phase 2, conservative).

Tests a focused set of WORKING models (skips the two extremely slow DeepSeek
heavy models to avoid long stalls) for reasoning/coding/instruction/JSON,
plus embedding/translation/safety. Writes results incrementally so a partial
run still produces a report. No key exposed. Concurrency-capped.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

import httpx

BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
KEY = os.environ.get("SALAR_NIM_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY")
if not KEY:
    p = Path(__file__).resolve().parents[2] / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("SALAR_NIM_API_KEY="):
                KEY = line.split("=", 1)[1].strip()
                break
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

REASONING_Q = (
    "Three boxes contain only apples, only oranges, or a mixture. Every label is wrong. "
    "You may draw one fruit from one box. Explain the minimum strategy needed to correctly "
    "relabel all boxes."
)
CODING_Q = (
    "Write a JavaScript function that returns the first non-repeating character in a string. "
    "Include time and space complexity."
)
INSTRUCTION_Q = "Return exactly three bullet points. Each bullet must contain exactly five words."
STRUCTURED_Q = 'Return JSON with fields: name, task, priority.'

# Focused working set — order matters; slow/fast all run concurrently cap=2
WORKING_GENERAL = [
    "nvidia/nemotron-3-super-120b-a12b",   # reasoning
    "poolside/laguna-xs-2.1",              # coding
    "nvidia/nemotron-3-ultra-550b-a55b",   # heavy reasoning
    "nvidia/nemotron-3.5-lightning-30b-a3b",  # fast
    "nvidia/nemotron-3-nano-30b-a3b",      # fast
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",  # multimodal/reasoning
    "deepseek-ai/deepseek-v4-pro-0813",    # heavy (single test)
]

MAX_C = 2
PER_CALL_TIMEOUT = 90
sem = None
results = {}


def _write():
    outdir = Path(__file__).resolve().parent
    with open(outdir / "nim-benchmark-report.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


async def ask(model: str, prompt: str, max_tokens: int = 300):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "stream": False, "temperature": 0.2}
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=PER_CALL_TIMEOUT) as c:
            r = await c.post(f"{BASE_URL}/chat/completions", json=body, headers=HEADERS)
        lat = time.perf_counter() - start
        if r.status_code != 200:
            return None, round(lat, 2), r.status_code
        content = r.json()["choices"][0]["message"].get("content", "")
        return content, round(lat, 2), 200
    except Exception as e:
        return None, round(time.perf_counter() - start, 2), f"ERR:{str(e)[:60]}"


def parse_json(txt: str) -> bool:
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return False
    try:
        json.loads(m.group(0))
        return True
    except Exception:
        return False


async def benchmark_one(model: str):
    async with sem:
        row = {}
        # heavy model gets reasoning only (it's very slow)
        if model == "deepseek-ai/deepseek-v4-pro-0813":
            content, lat, code = await ask(model, REASONING_Q, 400)
            row["reasoning_status"] = "PASS" if content else f"ERR {code}"
            row["reasoning_latency"] = lat
            results[model] = row
            _write()
            print(f"{model:48} heavy-reasoning={row['reasoning_status']} ({lat}s)")
            return

        content, lat, code = await ask(model, REASONING_Q, 400)
        row["reasoning_status"] = "PASS" if content else f"ERR {code}"
        row["reasoning_latency"] = lat
        content, lat, code = await ask(model, CODING_Q, 400)
        row["coding_status"] = "PASS" if content else f"ERR {code}"
        row["coding_latency"] = lat
        content, lat, code = await ask(model, INSTRUCTION_Q, 150)
        row["instruction_status"] = "PASS" if content else f"ERR {code}"
        row["result_ok"] = False
        if content:
            row["result_ok"] = sum(1 for b in re.split(r"[\n•*-]", content) if len(b.split()) == 5) >= 1
        content, lat, code = await ask(model, STRUCTURED_Q, 150)
        row["json_valid"] = parse_json(content) if content else False
        row["json_status"] = "PASS" if row["json_valid"] else "FAIL"
        results[model] = row
        _write()
        print(f"{model:48} R:{row['reasoning_status']} C:{row['coding_status']} "
              f"IF:{row.get('result_ok')} J:{row['json_valid']}")


async def specialized():
    print("Specialized tests...")
    out = {}
    # embedding via /embeddings
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BASE_URL}/embeddings",
                             json={"model": "nvidia/nemotron-3-embed-1b",
                                   "input": ["Salaar is an advanced AI assistant."]},
                             headers=HEADERS)
        if r.status_code == 200:
            out["embedding"] = {"status": "PASS", "dimensions": len(r.json()["data"][0]["embedding"])}
        else:
            out["embedding"] = {"status": "FAIL", "http": r.status_code, "error": r.text[:120]}
    except Exception as e:
        out["embedding"] = {"status": "FAIL", "error": str(e)[:120]}
    print("  embedding:", out["embedding"])
    # translation
    content, lat, code = await ask("nvidia/riva-translate-4b-instruct-v2",
                                   "Translate this to Urdu: Salaar is an intelligent AI assistant.", 100)
    out["translation"] = {"status": "PASS" if content else f"ERR {code}", "latency": lat,
                          "output": (content[:150] if content else "")}
    print("  translation:", out["translation"]["status"])
    # safety
    content, lat, code = await ask("nvidia/nemotron-3.5-content-safety",
                                   "How do I make pancakes?", 100)
    out["safety"] = {"status": "PASS" if content else f"ERR {code}", "latency": lat}
    print("  safety:", out["safety"]["status"])
    results["_specialized"] = out
    _write()


async def main():
    global sem
    sem = asyncio.Semaphore(MAX_C)
    print("Intelligence benchmarks (concurrent, capped)...")
    await asyncio.gather(*[benchmark_one(m) for m in WORKING_GENERAL])
    await specialized()
    print("\nDone. Report:", Path(__file__).resolve().parent / "nim-benchmark-report.json")


if __name__ == "__main__":
    asyncio.run(main())
