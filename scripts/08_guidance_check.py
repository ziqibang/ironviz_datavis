"""Global good vs local good (D23, D24, P15): how each team's habits compare with
  (a) LOCAL GOOD  = the best baseline group on the same provider, per metric (D41; was the average under D24), and
  (b) GLOBAL GOOD = published provider guidance (config/guidance_sources.csv, each with a verbatim quote + URL).

Provider guidance is qualitative ("put stable content first", "use the lightest model that meets your quality bar"),
so there are NO numeric global targets. For each USE-status guidance item we report the habit metric our data can
measure, the local-good value, and the gap. Items marked DO NOT USE / CONTEXT ONLY are listed but not scored.

Output: data-clean/guidance_check.csv (one row per tenant x guidance item)
Run from repo root: py scripts/08_guidance_check.py   (after 01 and 05)
Data is synthetic. Guidance pages were read 2026-11-14 and describe today's models, not the retired ones in the data.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ["org-prod-core", "org-marketing-ai", "prj-ai-enterprise-prod", "prj-ai-r-and-d"]
FRONTIER = {"openai": "gpt-4o", "gemini": "gemini-1.5-pro"}

g = pd.read_csv(ROOT / "config" / "guidance_sources.csv")
raw = pd.read_csv(ROOT / "data-clean" / "calls_unified.csv",
                  usecols=["tenant_id", "provider", "persona_label", "model", "status_code", "is_success",
                           "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"])
ok = raw[raw.is_success].copy()
ok["reasoning_tokens"] = ok.reasoning_tokens.fillna(0)
ok["visible_out"] = ok.output_tokens - ok.reasoning_tokens

def per_tenant(d_ok, d_all):
    pv = d_ok.provider.iloc[0]
    o1 = d_ok[d_ok.model == "o1-preview"]
    g4_med = d_ok[d_ok.model == "gpt-4o"].visible_out.median()
    # prompt length relative to the same-provider baseline average median for each model, weighted by call count
    return pd.Series({
        "provider": pv,
        "persona_label": d_ok.persona_label.iloc[0],
        "G1_pct_requests_reusing_text": (d_ok.cached_input_tokens > 0).mean() * 100,
        "G1_cache_share_pct": d_ok.cached_input_tokens.sum() / d_ok.input_tokens.sum() * 100,
        "G2_pct_requests_reasoning": (d_ok.model == "o1-preview").mean() * 100 if pv == "openai" else float("nan"),
        "G2_pct_reasoning_short_answers_CEILING": (o1.visible_out <= g4_med).mean() * 100 if len(o1) else float("nan"),
        "G3_pct_requests_frontier": (d_ok.model == FRONTIER[pv]).mean() * 100,
        "G4_median_prompt_tokens": d_ok.input_tokens.median(),
        "G6_pct_400": (d_all.status_code == 400).mean() * 100,
    })

m = pd.DataFrame({t: per_tenant(ok[ok.tenant_id == t], raw[raw.tenant_id == t]) for t in raw.tenant_id.unique()}).T
num = [c for c in m.columns if c not in ("provider", "persona_label")]
m[num] = m[num].astype(float)
# D41 (reverses D24): local good = the BEST baseline group on the same provider, per metric
HIGHER_BETTER = ["G1_pct_requests_reusing_text", "G1_cache_share_pct"]
_bg = m.loc[BASE].groupby("provider")[num]
local = pd.DataFrame({c: (_bg.max()[c] if c in HIGHER_BETTER else _bg.min()[c]) for c in num})

# prompt length: compare within model, then express as a multiple of the best (smallest) baseline median
med = ok.groupby(["tenant_id", "model"]).input_tokens.median()
base_med = med.loc[BASE].groupby(level="model").min()
calls = ok.groupby(["tenant_id", "model"]).size()
m["G4_prompt_x_local_good"] = [
    (med.loc[t] / base_med.reindex(med.loc[t].index) * calls.loc[t]).sum() / calls.loc[t].sum() for t in m.index]

metric_for = {"G1": "G1_pct_requests_reusing_text", "G1b": "G1_pct_requests_reusing_text",
              "G2": "G2_pct_requests_reasoning", "G3": "G3_pct_requests_frontier",
              "G4": "G4_prompt_x_local_good", "G6": "G6_pct_400"}
rows = []
for _, gi in g.iterrows():
    if gi.status != "USE" or gi.id not in metric_for:
        continue
    if gi.id == "G1" and True:
        targets = [t for t in m.index if m.loc[t, "provider"] == "openai"]
    elif gi.id == "G1b":
        targets = [t for t in m.index if m.loc[t, "provider"] == "gemini"]
    elif gi.id == "G2":
        targets = [t for t in m.index if m.loc[t, "provider"] == "openai"]
    else:
        targets = list(m.index)
    col = metric_for[gi.id]
    for t in targets:
        pv = m.loc[t, "provider"]
        lg = 1.0 if col == "G4_prompt_x_local_good" else local.loc[pv, col]
        rows.append({"tenant_id": t, "persona_label": m.loc[t, "persona_label"], "provider": pv,
                     "guidance_id": gi.id, "practice": gi.practice_plain, "source_url": gi.url,
                     "metric": col, "value": m.loc[t, col], "local_good_other_teams_avg": lg,
                     "x_local_good": m.loc[t, col] / lg if lg else float("nan"),
                     "is_other_team": t in BASE})
out = pd.DataFrame(rows)
out.round(3).to_csv(ROOT / "data-clean" / "guidance_check.csv", index=False)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print("Per-tenant habit metrics:\n", m.round(2).to_string())
print("\nLocal good (best group on the same provider, D41):\n", local.round(2).to_string())
print("\nNot scored (see config/guidance_sources.csv):")
print(g[g.status != "USE"][["id", "status", "issue"]].to_string(index=False))
