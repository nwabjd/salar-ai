"""
SALAAR — NVIDIA NIM diagnostic & benchmark (isolated, removable).

Reads the API key only from env / .env. NEVER prints the key.
Conservative: small prompts, MAX_CONCURRENT=2, <=2 retries, no hammering.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Config (never hard-code the key)
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
KEY = os.environ.get("NVIDIA_NIM_API_KEY") or os.environ.get("SALAR_NIM_API_KEY")
if not KEY:
    # try .env files in repo root
    for p in (Path(__file__).resolve().parents[2] / ".env",):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("SALAR_NIM_API_KEY="):
                    KEY = line.split("=", 1)[1].strip()
                    break
            if KEY:
                break

MAX_CONCURRENT = 2
RETRIES = 2
ERROR_NO_KEY = 60.0

# semaphore created lazily inside the running loop (see run_all)

HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Model inventory (discovery-first; ids may be corrected via /v1/models)
# ---------------------------------------------------------------------------
MODELS = [
    # general / reasoning
    "deepseek-ai/deepseek-v4-pro-0813",
    "deepseek-ai/deepseek-v4-flash-0731",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "google/gemma-4-31b-it",
    "stepfun-ai/step-3.7-flash",
    "poolside/laguna-xs-2.1",
    # multimodal
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "meta/muse-glimmer-30b",
    "google/diffusiongemma-26b-a4b-it",
    # vision / specialized
    "nvidia/ising-calibration-1.5-31b",
    "nvidia/ising-calibration-1-35b-a3b",
    "nvidia/cosmos3-nano",
    "nvidia/cosmos3-nano-reasoner",
    "nvidia/cosmos-transfer2.5-2b",
    # embedding
    "nvidia/nemotron-3-embed-1b",
    # translation
    "nvidia/riva-translate-4b-instruct-v2",
    # safety
    "nvidia/nemotron-3.5-content-safety",
    # specialized services
    "nvidia/synthetic-video-detector",
    "nvidia/active-speaker-detection",
]

CATEGORY = {
    "deepseek-ai/deepseek-v4-pro-0813": "REASONING",
    "deepseek-ai/deepseek-v4-flash-0731": "GENERAL",
    "nvidia/nemotron-3.5-lightning-30b-a3b": "GENERAL",
    "nvidia/nemotron-3-ultra-550b-a55b": "REASONING",
    "nvidia/nemotron-3-super-120b-a12b": "REASONING",
    "nvidia/nemotron-3-nano-30b-a3b": "GENERAL",
    "google/gemma-4-31b-it": "GENERAL",
    "stepfun-ai/step-3.7-flash": "CODING",
    "poolside/laguna-xs-2.1": "CODING",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": "MULTIMODAL",
    "meta/muse-glimmer-30b": "MULTIMODAL",
    "google/diffusiongemma-26b-a4b-it": "VISION",
    "nvidia/ising-calibration-1.5-31b": "CALIBRATION",
    "nvidia/ising-calibration-1-35b-a3b": "CALIBRATION",
    "nvidia/cosmos3-nano": "VIDEO",
    "nvidia/cosmos3-nano-reasoner": "VIDEO",
    "nvidia/cosmos-transfer2.5-2b": "SPECIALIZED",
    "nvidia/nemotron-3-embed-1b": "EMBEDDING",
    "nvidia/riva-translate-4b-instruct-v2": "TRANSLATION",
    "nvidia/nemotron-3.5-content-safety": "SAFETY",
    "nvidia/synthetic-video-detector": "SPECIALIZED",
    "nvidia/active-speaker-detection": "SPECIALIZED",
}

results: Dict[str, Dict[str, Any]] = {}
sem = None


def classify_error(status: Optional[int], text: str) -> str:
    t = text.lower()
    if status == 401 or status == 403:
        return "AUTHENTICATION_FAILURE"
    if status == 400:
        if "model not found" in t or "unknown model" in t:
            return "INVALID_MODEL_ID"
        return "REQUEST_FORMAT_ERROR"
    if status == 404:
        return "ENDPOINT_NOT_SUPPORTED"
    if status == 429 or "rate" in t or "quota" in t:
        return "RATE_LIMIT"
    if status >= 500:
        return "PROVIDER_ERROR"
    return "UNKNOWN"


async def chat_test(model: str) -> Dict[str, Any]:
    """Basic chat completions connectivity + streaming test."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: SALAAR NIM TEST OK"}],
        "max_tokens": 32,
        "stream": False,
    }
    start = time.perf_counter()
    errors = []
    for attempt in range(RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{BASE_URL}/chat/completions", json=body, headers=HEADERS)
            if r.status_code in (401, 403, 404):
                return {"status": "FAIL", "error": classify_error(r.status_code, r.text),
                        "http": r.status_code, "latency": time.perf_counter() - start,
                        "endpoint": "/chat/completions"}
            if r.status_code in (429,):
                return {"status": "RATE_LIMIT", "error": "RATE_LIMIT", "http": 429,
                        "latency": time.perf_counter() - start}
            if r.status_code >= 500 and attempt < RETRIES:
                errors.append(r.status_code)
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return {"status": "FAIL", "error": classify_error(r.status_code, r.text),
                        "http": r.status_code, "latency": time.perf_counter() - start}
            data = r.json()
            content = data["choices"][0]["message"].get("content", "")
            total = time.perf_counter() - start
            # streaming check
            ttft, stream_ok = await stream_probe(model)
            return {"status": "PASS", "content": content, "latency": round(total, 2),
                    "ttft": ttft, "streaming": stream_ok, "endpoint": "/chat/completions",
                    "http": 200}
        except httpx.TimeoutException as e:
            return {"status": "FAIL", "error": "TIMEOUT", "latency": time.perf_counter() - start}
        except Exception as e:
            if attempt < RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return {"status": "FAIL", "error": "NETWORK_ERROR", "detail": str(e)[:120],
                    "latency": time.perf_counter() - start}
    return {"status": "FAIL", "error": "UNKNOWN", "latency": time.perf_counter() - start}


async def stream_probe(model: str):
    body = {"model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8, "stream": True}
    start = time.perf_counter()
    ttft = None
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{BASE_URL}/chat/completions",
                                     json=body, headers=HEADERS) as r:
                if r.status_code != 200:
                    return None, False
                async for line in r.aiter_lines():
                    if line.startswith("data:") and "content" in line:
                        ttft = time.perf_counter() - start
                        break
        return (round(ttft, 2) if ttft else None), True
    except Exception:
        return None, False


async def embed_test(model: str):
    body = {"model": model, "input": ["Salaar is an advanced AI assistant."]}
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{BASE_URL}/embeddings", json=body, headers=HEADERS)
        if r.status_code != 200:
            return {"status": "FAIL", "error": classify_error(r.status_code, r.text),
                    "http": r.status_code, "endpoint": "/embeddings"}
        data = r.json()
        dims = len(data["data"][0]["embedding"])
        return {"status": "PASS", "dimensions": dims, "latency": round(time.perf_counter() - start, 2),
                "endpoint": "/embeddings"}
    except Exception as e:
        return {"status": "FAIL", "error": "NETWORK_ERROR", "detail": str(e)[:120]}


async def run_all():
    global sem
    sem = asyncio.Semaphore(MAX_CONCURRENT)  # created inside the running loop
    key_present = bool(KEY)
    if not key_present:
        print("NVIDIA_NIM_API_KEY is not configured.")
        return

    tasks = []
    for model in MODELS:
        tasks.append(test_model(model))
    await asyncio.gather(*tasks)


async def test_model(model: str):
    async with sem:
        cat = CATEGORY.get(model, "UNKNOWN")
        row = {"model": model, "category": cat}
        # embedding models use the embeddings endpoint
        if cat == "EMBEDDING":
            res = await embed_test(model)
            row.update(res)
        else:
            res = await chat_test(model)
            row.update(res)
        results[model] = row
        status = row.get("status")
        lat = row.get("latency")
        extra = ""
        if row.get("streaming"):
            extra = f" ttft={row.get('ttft')}s"
        print(f"{model:55} {status:12} {row.get('error','')} {lat}{extra}")


async def main():
    if not KEY:
        print("NVIDIA_NIM_API_KEY is not configured.")
        return
    print(f"Base: {BASE_URL}")
    print(f"{'model':55} {'status':12} {'error':20} latency")
    print("-" * 100)
    await run_all()
    outdir = Path(__file__).resolve().parent
    with open(outdir / "nim-diagnostic-report.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nReport written to:", outdir / "nim-diagnostic-report.json")
    summarize()


def summarize():
    working = [m for m, r in results.items() if r.get("status") == "PASS"]
    rate = [m for m, r in results.items() if r.get("status") == "RATE_LIMIT"]
    fail = [m for m, r in results.items() if r.get("status") == "FAIL"]
    print("\nSALAAR NIM DIAGNOSTIC COMPLETE")
    print(f"Models tested: {len(results)}  Working: {len(working)}  "
          f"Rate limited: {len(rate)}  Failed: {len(fail)}")
    if working:
        print("\nWorking:")
        for m in sorted(working, key=lambda x: results[x].get("latency", 999)):
            print(f"  {m:55} {results[m].get('latency')}s")
    if fail:
        print("\nFailed:")
        for m in fail:
            print(f"  {m:55} {results[m].get('error')} ({results[m].get('http')})")


if __name__ == "__main__":
    asyncio.run(main())
