"""Step 2c / D11: find the 'local good' benchmark among the 4 baseline tenants.

Dev (org-engineering-dev) and Sandbox (prj-ai-sandbox-testing) are the outliers; the other 4 are ranked on
normalized efficiency metrics. Cost and energy-per-call depend on provider/model family, so those are ranked
WITHIN provider; provider-neutral behaviour metrics (cache, errors) are ranked across all 4.
'Local good' = the best observed value of each metric among the 4 (a CMU-internal, achievable target).
NOTE: scripts/04 showed differences among these 4 are NOT practically meaningful - the ranking is a tie-break,
the benchmark values are what matter.
Run from repo root: py scripts/05_local_best.py [pricing_tag]
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
tag = sys.argv[1] if len(sys.argv) > 1 else "pricing_list"
df = pd.read_csv(ROOT / "data-clean" / f"calls_costed_carbon__{tag}.csv")
BASE = ["org-prod-core", "org-marketing-ai", "prj-ai-enterprise-prod", "prj-ai-r-and-d"]
OUTLIERS = ["org-engineering-dev", "prj-ai-sandbox-testing"]

def metrics(d):
    s = d[d.is_success]
    return pd.Series({
        "provider": d.provider.iloc[0],
        "pct_400": (d.status_code == 400).mean() * 100,
        "pct_429": (d.status_code == 429).mean() * 100,
        "cache_share_pct": s.cached_input_tokens.sum() / s.input_tokens.sum() * 100,
        "pct_calls_any_cache": (s.cached_input_tokens > 0).mean() * 100,
        "median_input_tokens": s.input_tokens.median(),
        "pct_calls_premium_model": s.model.isin(["gpt-4o", "o1-preview", "gemini-1.5-pro"]).mean() * 100,
        "pct_calls_reasoning_model": (s.model == "o1-preview").mean() * 100,
        "cost_per_success_usd": s.cost_usd.mean(),
        "wh_per_success_central": s.wh_central.mean(),
        "gco2e_per_success_central": s.gco2e_central.mean(),
    })

m = df.groupby("tenant_id").apply(metrics)
m["persona_label"] = df.groupby("tenant_id").persona_label.first()

LOWER_BETTER = ["pct_400", "pct_429", "median_input_tokens", "pct_calls_premium_model",
                "cost_per_success_usd", "wh_per_success_central"]
HIGHER_BETTER = ["cache_share_pct", "pct_calls_any_cache"]
WITHIN_PROVIDER = ["median_input_tokens", "pct_calls_premium_model", "cost_per_success_usd", "wh_per_success_central"]

b = m.loc[BASE].copy()
ranks = pd.DataFrame(index=b.index)
for col in LOWER_BETTER + HIGHER_BETTER:
    asc = col in LOWER_BETTER
    if col in WITHIN_PROVIDER:
        ranks[col] = b.groupby("provider")[col].rank(ascending=asc)  # 1 or 2 within provider
        ranks[col] = (ranks[col] - 1) / 1 * 3 + 1                     # rescale to 1..4 for comparability
    else:
        ranks[col] = b[col].rank(ascending=asc)
b["mean_rank"] = ranks.mean(axis=1)
b = b.sort_values("mean_rank")

# local-good benchmark: best value per metric among the 4 (per provider where model-dependent)
bench = {}
for col in LOWER_BETTER + HIGHER_BETTER:
    best = (b[col].min() if col in LOWER_BETTER else b[col].max())
    bench[col] = best
# (Superseded by D41 below) D24: the comparison point for outliers is now "what CMU's other teams already do" = the AVERAGE of the baseline
# tenants on the same provider (the 4 are statistically indistinguishable, so best-of-4 was a composite of noise).
# The best-of-4 values above are kept for reference only.
# D41 (reverses D24): local good = the BEST baseline group on the same provider, per metric (matches chart 1).
_cols = WITHIN_PROVIDER + ["pct_400", "cache_share_pct", "pct_calls_any_cache"]
bench_prov = pd.DataFrame({c: (b.groupby("provider")[c].min() if c in LOWER_BETTER else b.groupby("provider")[c].max())
                           for c in _cols})

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
print("ALL 6 TENANTS:\n", m.round(3).to_string())
print("\nBASELINE-4 RANKING (lower mean_rank = better):\n", b[["persona_label", "provider", "mean_rank"]].round(2).to_string())
print("\nRank detail:\n", ranks.loc[b.index].round(1).to_string())
print("\nLOCAL-GOOD benchmark (best of 4, provider-neutral metrics):")
for k in ["pct_400", "pct_429", "cache_share_pct", "pct_calls_any_cache"]:
    print(f"  {k}: {bench[k]:.2f}")
print("Local-good per provider (model-dependent metrics):\n", bench_prov.round(4).to_string())

gap = m.loc[OUTLIERS, ["persona_label", "provider", "pct_400", "cache_share_pct", "median_input_tokens",
                       "pct_calls_premium_model", "cost_per_success_usd", "wh_per_success_central"]].copy()
for col in ["cost_per_success_usd", "wh_per_success_central", "median_input_tokens", "pct_calls_premium_model",
            "pct_400", "cache_share_pct"]:
    gap[col + "_vs_local_good_x"] = [m.loc[t, col] / bench_prov.loc[m.loc[t, "provider"], col] for t in OUTLIERS]
    gap[col + "_local_good"] = [bench_prov.loc[m.loc[t, "provider"], col] for t in OUTLIERS]
print("Local good per provider (BEST group on the same provider, D41):\n", bench_prov.round(4).to_string())
print("\nOUTLIERS vs local good (x = multiple of the best group on the same provider, D41):\n", gap.round(3).to_string())

m.round(4).to_csv(ROOT / "data-clean" / "persona_metrics.csv")
b.round(4).to_csv(ROOT / "data-clean" / "local_best_ranking.csv")
gap.round(4).to_csv(ROOT / "data-clean" / "outliers_vs_local_good.csv")
