"""
SALAAR — consolidate NIM diagnostic into final report + routing recommendations.
Reads the three phase JSON reports, computes weighted rankings, writes:
  - nim-diagnostic-final.json
  - nim-diagnostic-report.md
No key exposed.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

P1 = json.loads((HERE / "nim-diagnostic-report.json").read_text())
P2 = json.loads((HERE / "nim-benchmark-report.json").read_text())
P3 = json.loads((HERE / "nim-probe-report.json").read_text())

# weights: quality .40  reliability .25  latency .20  instruction .15
W_Q, W_R, W_L, W_I = 0.40, 0.25, 0.20, 0.15


def quality_score(model: str) -> float:
    row = P2.get(model, {})
    if not row:
        return 0.5
    s = 0.0
    if row.get("reasoning_status") == "PASS":
        s += 0.25
    if row.get("coding_status") == "PASS":
        s += 0.25
    if row.get("result_ok"):
        s += 0.25
    if row.get("json_valid"):
        s += 0.25
    return s


def latency_score(lat: float) -> float:
    if lat is None:
        return 0.0
    if lat <= 1:
        return 1.0
    if lat <= 5:
        return 0.8
    if lat <= 15:
        return 0.5
    if lat <= 40:
        return 0.3
    return 0.1


def overall(model: str) -> tuple:
    p1 = P1.get(model, {})
    lat = p1.get("latency")
    rel = 1.0 if p1.get("status") == "PASS" else 0.0
    # probe/latency reliability discount for very slow or unreliable
    if model in ("deepseek-ai/deepseek-v4-pro-0813",):
        rel = 0.7
    qual = quality_score(model)
    inst = (lambda v: 1.0 if v else 0.0)(P2.get(model, {}).get("result_ok"))
    score = (W_Q * qual) + (W_R * rel) + (W_L * latency_score(lat)) + (W_I * inst)
    return round(score, 3), lat, qual, rel, inst


FINAL = {}

# 1. working models from phase 1
working = {m: r for m, r in P1.items()
           if r.get("status") == "PASS" and not m.startswith("_")}

# 2. add probe-pass models
for row in P3:
    if row.get("status") == "PASS":
        working.setdefault(row["model"], {"status": "PASS", "latency": row.get("latency")})

ranked = []
for model, r in working.items():
    score, lat, qual, rel, inst = overall(model)
    entry = {
        "model": model,
        "category": r.get("category", "GENERAL"),
        "status": "PASS",
        "latency_s": lat,
        "streaming": r.get("streaming"),
        "quality_score": round(qual, 2),
        "reliability": rel,
        "instruction_following": inst,
        "overall_score": score,
    }
    ranked.append(entry)

ranked.sort(key=lambda x: x["overall_score"], reverse=True)

# Routing recommendations
def recommend() -> list:
    recs = []
    by_cat = {}
    for e in ranked:
        recs.append({
            "route": "GENERAL_CHAT",
            "priority": list(range(len(ranked))).index(ranked.index(e)) if False else len(recs) + 1,
            "model": e["model"],
            "reason": f"overall {e['overall_score']}, latency {e['latency_s']}s, "
                      f"quality {e['quality_score']}, streaming {e['streaming']}",
        })
    return recs


FINAL["summary"] = {
    "base_url": "https://integrate.api.nvidia.com/v1",
    "timestamp": None,
    "account_models_listed": 84,
    "models_tested": len(P1) + len(P3),
    "models_working": len(ranked),
    "weighting": {"quality": W_Q, "reliability": W_R, "latency": W_L, "instruction": W_I},
    "notes": [
        "Several catalog models return 404 'Not found for this account' (not provisioned on this plan).",
        "Embedding models (e.g. nemotron-3-embed-1b) hang on the generic /embeddings shape; not verified.",
        "nemotron-parse requires multimodal (document) input, not plain text.",
        "cosmos/ising/video-detector models use non-chat endpoints; excluded from chat routing.",
    ],
}
FINAL["rankings"] = ranked
FINAL["working_models"] = [e["model"] for e in ranked]
FINAL["recommended_routing"] = recommend()
FINAL["failed_models"] = [m for m, r in P1.items() if r.get("status") != "PASS"]

with open(HERE / "nim-diagnostic-final.json", "w") as f:
    json.dump(FINAL, f, indent=2)

# ---- Markdown report ----
lines = []
lines.append("# SALAAR NVIDIA NIM Diagnostic Report\n")
lines.append("Base: `https://integrate.api.nvidia.com/v1`  \n")
lines.append(f"Models listed on account: 84  |  Tested: {len(P1) + len(P3)}  |  Working: {len(ranked)}\n")
lines.append("## Working models (ranked)\n")
lines.append("| Rank | Model | Score | Latency | Quality | Streaming |")
lines.append("|------|-------|-------|---------|---------|-----------|")
for i, e in enumerate(ranked, 1):
    lines.append(f"| {i} | {e['model']} | {e['overall_score']} | {e['latency_s']}s | "
                 f"{e['quality_score']} | {e['streaming']} |")
lines.append("\n## Recommended SALAAR routing (NIM-only)\n")
for r in FINAL["recommended_routing"]:
    lines.append(f"- **{r['model']}** -> {r['reason']}")
lines.append("\n## Failed / not-provisioned\n")
for m, r in P1.items():
    if r.get("status") != "PASS" and not m.startswith("_"):
        lines.append(f"- {m}: {r.get('error', r.get('status'))} (http {r.get('http')})")

(HERE / "nim-diagnostic-report.md").write_text("\n".join(lines))
print("Wrote:")
print("  nim-diagnostic-final.json")
print("  nim-diagnostic-report.md")
print(f"\nWorking: {len(ranked)} models")
for i, e in enumerate(ranked, 1):
    print(f"  {i}. {e['model']:48} score={e['overall_score']} lat={e['latency_s']}s qual={e['quality_score']}")
