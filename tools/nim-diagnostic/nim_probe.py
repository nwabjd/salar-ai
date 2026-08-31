"""
Quick connectivity probe on newly-discovered / high-value NIM models.
Writes nim-probe-report.json. No key exposed.
"""
from __future__ import annotations

import asyncio, json, os, time
from pathlib import Path
import httpx

BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
KEY = os.environ.get("SALAR_NIM_API_KEY")
if not KEY:
    for line in (Path(__file__).resolve().parents[2] / ".env").read_text().splitlines():
        if line.startswith("SALAR_NIM_API_KEY="):
            KEY = line.split("=", 1)[1].strip(); break
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

PROBE = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "moonshotai/kimi-k3",
    "moonshotai/kimi-k2.6",
    "minimaxai/minimax-m3",
    "nvidia/nemotron-parse",
    "mistralai/mistral-nemotron",
    "nvidia/nemotron-4-340b-instruct",
    "writer/palmyra-creative-122b",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "google/gemma-3-12b-it",
]

async def probe(model: str):
    body = {"model": model, "messages": [{"role": "user", "content": "Reply with exactly: SALAAR NIM PROBE OK"}],
            "max_tokens": 24, "stream": False}
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BASE_URL}/chat/completions", json=body, headers=HEADERS)
        lat = round(time.perf_counter() - start, 2)
        if r.status_code == 200:
            return {"model": model, "status": "PASS", "latency": lat}
        return {"model": model, "status": "FAIL", "http": r.status_code, "error": r.text[:120], "latency": lat}
    except Exception as e:
        return {"model": model, "status": "FAIL", "error": str(e)[:100],
                "latency": round(time.perf_counter() - start, 2)}

async def main():
    out = await asyncio.gather(*[probe(m) for m in PROBE])
    for row in sorted(out, key=lambda x: x.get("latency", 999)):
        print(f"{row['model']:48} {row['status']:8} {row.get('latency')}s {row.get('error','')}")
    with open(Path(__file__).resolve().parent / "nim-probe-report.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nProbe report:", Path(__file__).resolve().parent / "nim-probe-report.json")

asyncio.run(main())
