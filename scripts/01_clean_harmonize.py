"""Step 1: clean + harmonize OpenAI and Gemini telemetry into one call-level table.

Follows the "Unified Cross-Provider Mapping Guide" in
data-uncleaned/Fall 2026 - CMU Student IronViz_ Data Dictionary & Quality Guide.docx

Run from repo root:  py scripts/01_clean_harmonize.py
Output: data-clean/calls_unified.csv  +  data-clean/qa_report.txt
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data-uncleaned"
OUT = ROOT / "data-clean"
OUT.mkdir(exist_ok=True)

# --- Persona mapping: KEEP 6 TENANTS SEPARATE (user decision 2026-11-14) ------------
# persona_label and merge_candidate are PROPOSALS, pending user confirmation.
TENANTS = {
    #  tenant_id                 provider   persona_label (proposed)        environment   merge_candidate (proposed)
    "org-engineering-dev":    ("openai", "Engineering / Developers",      "dev",         "Dev & Sandbox"),
    "prj-ai-sandbox-testing": ("gemini", "Sandbox Testers",               "sandbox",     "Dev & Sandbox"),
    "org-prod-core":          ("openai", "Core Production Services",      "prod",        "Production Services"),
    "prj-ai-enterprise-prod": ("gemini", "Enterprise Production",         "prod",        "Production Services"),
    "org-marketing-ai":       ("openai", "Marketing / Communications",    "business",    "Marketing / Communications (no Gemini twin)"),
    "prj-ai-r-and-d":         ("gemini", "Researchers (R&D)",             "research",    "Researchers (no OpenAI twin)"),
}


def parse_json(s):
    """Defensive parse: blank/NULL/malformed -> None (data guide recommends try/except)."""
    if not isinstance(s, str) or not s.strip() or s.strip().lower() in ("null", "none"):
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def load_openai():
    df = pd.read_csv(RAW / "openai_pipeline_telemetry_raw.csv", dtype=str, keep_default_na=False)
    u = df["usage"].map(parse_json)
    e = df["error"].map(parse_json)
    return pd.DataFrame({
        "call_id": df["id"],
        "ts_utc": df["created_at"],
        "provider": "openai",
        "model": df["model"],
        "tenant_id": df["organization_id"],
        "status_code": df["status_code"],
        "error_type": e.map(lambda d: d.get("type") if d else None),
        "error_message": e.map(lambda d: d.get("message") if d else None),
        "usage_parse_ok": u.notna(),
        "input_tokens": u.map(lambda d: _dig(d, ("prompt_tokens",))),
        "output_tokens": u.map(lambda d: _dig(d, ("completion_tokens",))),
        "total_tokens": u.map(lambda d: _dig(d, ("total_tokens",))),
        "cached_input_tokens": u.map(lambda d: _dig(d, ("prompt_tokens_details", "cached_tokens"))),
        "reasoning_tokens": u.map(lambda d: _dig(d, ("completion_tokens_details", "reasoning_tokens"))),
    })


def load_gemini():
    df = pd.read_csv(RAW / "gemini_pipeline_telemetry_raw.csv", dtype=str, keep_default_na=False)
    u = df["usageMetadata"].map(parse_json)
    e = df["error_details"].map(parse_json)
    return pd.DataFrame({
        "call_id": df["response_id"],
        "ts_utc": df["timestamp"],
        "provider": "gemini",
        "model": df["model_version"],
        "tenant_id": df["gcp_project_id"],
        "status_code": df["http_response_code"],
        "error_type": e.map(lambda d: d.get("status") if d else None),
        "error_message": e.map(lambda d: d.get("message") if d else None),
        "usage_parse_ok": u.notna(),
        "input_tokens": u.map(lambda d: _dig(d, ("promptTokenCount",))),
        "output_tokens": u.map(lambda d: _dig(d, ("candidatesTokenCount",))),
        "total_tokens": u.map(lambda d: _dig(d, ("totalTokenCount",))),
        "cached_input_tokens": u.map(lambda d: _dig(d, ("cachedContentTokenCount",))),
        "reasoning_tokens": None,  # Gemini 1.5 does not report reasoning tokens
    })


def _dig(d, keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def main():
    raw_counts = {}
    frames = []
    for name, loader in (("openai", load_openai), ("gemini", load_gemini)):
        f = loader()
        raw_counts[name] = len(f)
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)

    # Types
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, format="ISO8601")
    df["status_code"] = pd.to_numeric(df["status_code"], errors="coerce").astype("Int64")
    for c in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # Derived fields
    df["date"] = df["ts_utc"].dt.date
    df["hour_utc"] = df["ts_utc"].dt.hour
    df["weekday"] = df["ts_utc"].dt.day_name()
    df["is_success"] = df["status_code"].eq(200)
    df["outcome"] = df["status_code"].map({200: "success", 400: "bad_request_400", 429: "rate_limited_429"}).fillna("other")
    # cached is a SUBSET of input (data guide) -> uncached = input - cached; never add cached to totals
    df["uncached_input_tokens"] = df["input_tokens"] - df["cached_input_tokens"]
    df["cache_hit_share"] = (df["cached_input_tokens"] / df["input_tokens"]).astype("Float64")

    t = df["tenant_id"].map(TENANTS)
    df["persona_label"] = t.map(lambda x: x[1] if isinstance(x, tuple) else "UNMAPPED")
    df["environment"] = t.map(lambda x: x[2] if isinstance(x, tuple) else "UNMAPPED")
    df["merge_candidate"] = t.map(lambda x: x[3] if isinstance(x, tuple) else "UNMAPPED")

    # --- QA checks (nothing dropped; issues are flagged + reported) ---
    s = df[df["is_success"]]
    f = df[~df["is_success"]]
    qa = {
        "raw rows (openai, gemini)": raw_counts,
        "unified rows": len(df),
        "duplicate call_id": int(df["call_id"].duplicated().sum()),
        "unmapped tenants": int((df["persona_label"] == "UNMAPPED").sum()),
        "status codes": df["status_code"].value_counts(dropna=False).to_dict(),
        "success rows with unparseable usage": int((~s["usage_parse_ok"]).sum()),
        "failed rows with non-null usage (should be 0)": int(f["usage_parse_ok"].sum()),
        "failed rows missing error payload": int(f["error_message"].isna().sum()),
        "cached > input (violates subset rule)": int((s["cached_input_tokens"] > s["input_tokens"]).sum()),
        "total != input + output": int((s["total_tokens"] != s["input_tokens"] + s["output_tokens"]).sum()),
        "openai reasoning > output": int((s["reasoning_tokens"] > s["output_tokens"]).sum()),
        "negative token values": int((s[["input_tokens", "output_tokens", "cached_input_tokens"]] < 0).any(axis=1).sum()),
        "date range": f'{df["ts_utc"].min()} -> {df["ts_utc"].max()}',
        "distinct dates": int(df["date"].nunique()),
        "error type x message": df.loc[~df["is_success"]].groupby(["provider", "status_code", "error_type", "error_message"]).size().to_dict(),
    }
    with open(OUT / "qa_report.txt", "w", encoding="utf-8") as fh:
        for k, v in qa.items():
            fh.write(f"{k}: {v}\n")
    df.drop(columns=["usage_parse_ok"]).to_csv(OUT / "calls_unified.csv", index=False)
    for k, v in qa.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
