"""Step 4 / D16: what-if scenarios -> how much cost and energy each lever could save, per persona.

LOCAL GOOD (outliers only: Engineering/Dev, Sandbox) - "match CMU's best group on the same provider" (D41):
targets = BEST baseline tenant on the SAME PROVIDER, per metric (D41 reverses D24's average; the
"average" wording on L1-L4 below now reads "best group").
  L1 cache     raise token-weighted cache share to the same-provider baseline average
  L2 prompt    shrink prompts (per model) to the average baseline median prompt size for that model
  L3 model mix move excess frontier-model calls (gpt-4o / gemini-1.5-pro) to the small model
               (gpt-4o-mini / gemini-1.5-flash) until the frontier share matches the same-provider baseline average;
               the calls moved are the ones with the smallest output (proxy for routine tasks)
  L4 errors    cut the 400 rate to the same-provider baseline average (reported as failed calls avoided; failed
               calls cost $0 / 0 Wh in this model, see B0b X12)
  L_all        L1 + L2 + L3
GLOBAL GOOD (all tenants) - provider guidance (cited in config/guidance_sources.csv) is qualitative, so there are
NO targets (D23). Each practice is sized PER UNIT of change (config/scenario_params.csv):
  G1 cache step   +10 points of token-weighted cache share for every tenant
  G2 route step   10% of each tenant's o1-preview calls answered by gpt-4o (hidden reasoning tokens dropped)
  Route ceiling   share of o1-preview calls whose answer is no longer than the tenant's median gpt-4o answer
                  (a data ceiling, never a target)
Removed in D23: the 50% cache target, the 50% reasoning reroute, the p75 output cap, and the G_all / LG_all totals.

Cost and energy use the same formulas and config files as 03_cost.py and 06_carbon.py.
Data is synthetic; energy is an ESTIMATE; some prices are unverified (B0b).
Run from repo root: py scripts/07_scenarios.py [config/pricing_X.csv]
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
pricing_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config" / "pricing_list.csv"
if not pricing_path.is_absolute():
    pricing_path = ROOT / pricing_path
tag = pricing_path.stem

price = pd.read_csv(pricing_path).set_index("model")
bench = pd.read_csv(ROOT / "config" / "energy_benchmarks.csv")
cp = pd.read_csv(ROOT / "config" / "carbon_params.csv").set_index("param")["value"]
sp = pd.read_csv(ROOT / "config" / "scenario_params.csv").set_index("param")["value"]

BASE = ["org-prod-core", "org-marketing-ai", "prj-ai-enterprise-prod", "prj-ai-r-and-d"]
OUTLIERS = ["org-engineering-dev", "prj-ai-sandbox-testing"]
FRONTIER = {"openai": "gpt-4o", "gemini": "gemini-1.5-pro"}
SMALL = {"openai": "gpt-4o-mini", "gemini": "gemini-1.5-flash"}
REASONING, REASONING_TO = "o1-preview", "gpt-4o"

# ---- energy coefficients (same exact 3-point solve as 06_carbon.py) ----
SIZES = np.array([[1, 100, 300], [1, 1000, 1000], [1, 10000, 1500]], float)
coef = {r.benchmark_model: np.linalg.solve(SIZES, [r.short_wh, r.medium_wh, r.long_wh]) for _, r in bench.iterrows()}
model_map = {k.split(":", 1)[1]: v for k, v in cp.items() if k.startswith("model_map:")}
LOW_SCALE = float(cp["low_energy_scale"])
SH_LO, SH_HI = float(cp["cached_input_energy_share_low"]), float(cp["cached_input_energy_share_high"])
GRID_C = float(cp["grid_g_per_kwh_central"])

raw = pd.read_csv(ROOT / "data-clean" / "calls_unified.csv")
s0 = raw[raw.is_success].copy()
s0["reasoning_tokens"] = s0["reasoning_tokens"].fillna(0)
s0 = s0[["tenant_id", "persona_label", "provider", "model", "input_tokens", "cached_input_tokens",
         "output_tokens", "reasoning_tokens"]].reset_index(drop=True)


def totals(s):
    """Per-tenant cost and energy for a (possibly modified) frame of successful calls."""
    p = price.loc[s.model]
    unc = (s.input_tokens - s.cached_input_tokens).to_numpy()
    cac, out = s.cached_input_tokens.to_numpy(), s.output_tokens.to_numpy()
    cost = (unc * p.usd_per_1m_input.to_numpy() + cac * p.usd_per_1m_cached_input.to_numpy()
            + out * p.usd_per_1m_output.to_numpy()) / 1e6
    c = np.array([coef[model_map[m]] for m in s.model])
    a, bi, bo = c[:, 0], c[:, 1], c[:, 2]
    hi = a + bi * (unc + cac * SH_HI) + bo * out
    lo = LOW_SCALE * (a + bi * (unc + cac * SH_LO) + bo * out)
    t = pd.DataFrame({"tenant_id": s.tenant_id, "cost_usd": cost, "wh_low": lo, "wh_high": hi,
                      "wh_central": (lo + hi) / 2})
    g = t.groupby("tenant_id").sum()
    out_df = pd.DataFrame({"cost_usd": g.cost_usd,
                           "kwh_low": g.wh_low / 1000, "kwh_central": g.wh_central / 1000, "kwh_high": g.wh_high / 1000})
    out_df["kgco2e_central"] = out_df.kwh_central * GRID_C / 1000
    return out_df


# ---- local-good targets (D41: best group on the same provider; was the average under D24/P14) ----
# AVERAGE of the baseline tenants on the SAME PROVIDER (OpenAI: prod-core + marketing; Gemini: enterprise-prod + r-and-d).
# Replaces the earlier best-of-4 targets: the four are statistically indistinguishable (script 04), so "best" was
# a composite of whichever tenant happened to be highest per metric, and the cache target crossed providers.
b = s0[s0.tenant_id.isin(BASE)]
PROVIDER_OF = s0.groupby("tenant_id").provider.first()
BASE_BY_PV = {pv: [t for t in BASE if PROVIDER_OF[t] == pv] for pv in FRONTIER}
# D41 (reverses D24): targets are the BEST baseline group on the same provider, per metric
# (cache: highest share; prompt size per model, frontier share, 400 rate: lowest). Matches chart 1.
cache_share = s0.groupby("tenant_id").apply(lambda d: d.cached_input_tokens.sum() / d.input_tokens.sum())
LOCAL_CACHE = {pv: cache_share[ts].max() for pv, ts in BASE_BY_PV.items()}
best_median = (b.groupby(["provider", "model", "tenant_id"]).input_tokens.median()
                .groupby(["provider", "model"]).min())  # best (smallest) baseline median prompt per model
frontier_share = s0.groupby(["provider", "tenant_id"]).apply(lambda d: (d.model == FRONTIER[d.name[0]]).mean())
LOCAL_FRONTIER = {pv: frontier_share[pv][ts].min() for pv, ts in BASE_BY_PV.items()}
pct400 = raw.groupby("tenant_id").apply(lambda d: (d.status_code == 400).mean())
LOCAL_400 = {pv: pct400[ts].min() for pv, ts in BASE_BY_PV.items()}
calls_all = raw.groupby("tenant_id").size()
visible = lambda d: d.output_tokens - d.reasoning_tokens


# ---- scenario transforms (each returns a modified copy) ----
def raise_cache(s, tenants, target=None, plus=None):
    """Raise a tenant's token-weighted cache share to its provider's target, or by `plus` (e.g. 0.10 = +10 points)."""
    s = s.copy()
    for t in tenants:
        m = s.tenant_id == t
        sh = s.loc[m, "cached_input_tokens"].sum() / s.loc[m, "input_tokens"].sum()
        tgt = min(1.0, sh + plus) if plus is not None else target[PROVIDER_OF[t]]
        if sh < tgt:
            f = (tgt - sh) / (1 - sh)  # same fraction of each call's uncached input becomes cached
            s.loc[m, "cached_input_tokens"] += (s.loc[m, "input_tokens"] - s.loc[m, "cached_input_tokens"]) * f
    return s


def trim_prompts(s, tenants):
    s = s.copy()
    for t in tenants:
        for (pv, mdl), target in best_median.items():
            m = (s.tenant_id == t) & (s.model == mdl)
            if not m.any():
                continue
            r = min(1.0, target / s.loc[m, "input_tokens"].median())
            s.loc[m, ["input_tokens", "cached_input_tokens"]] *= r
    return s


def move_calls(s, mask, n, new_model, drop_reasoning=False):
    idx = s[mask].assign(v=visible(s[mask])).sort_values("v").index[:max(0, int(round(n)))]
    s.loc[idx, "model"] = new_model
    if drop_reasoning:
        s.loc[idx, "output_tokens"] -= s.loc[idx, "reasoning_tokens"]
        s.loc[idx, "reasoning_tokens"] = 0
    return s


def fix_model_mix(s, tenants):
    s = s.copy()
    for t in tenants:
        tm = s.tenant_id == t
        pv = s.loc[tm, "provider"].iloc[0]
        excess = (s.loc[tm, "model"] == FRONTIER[pv]).mean() - LOCAL_FRONTIER[pv]
        s = move_calls(s, tm & (s.model == FRONTIER[pv]), excess * tm.sum(), SMALL[pv])
    return s


def route_reasoning(s, share):
    s = s.copy()
    for t in s.tenant_id.unique():
        m = (s.tenant_id == t) & (s.model == REASONING)
        s = move_calls(s, m, share * m.sum(), REASONING_TO, drop_reasoning=True)
    return s


ALL = list(s0.tenant_id.unique())
# Global good (D23): NO invented targets. Provider guidance is qualitative (config/guidance_sources.csv), so each
# practice is sized PER UNIT of change. The reader scales it; we never claim how far CMU "should" go.
G_CACHE_STEP = float(sp["global_cache_step_points"])      # +10 points of cache share
G_ROUTE_STEP = float(sp["global_reasoning_route_step"])   # 10% of reasoning calls answered by gpt-4o instead
L_all = lambda s: fix_model_mix(trim_prompts(raise_cache(s, OUTLIERS, LOCAL_CACHE), OUTLIERS), OUTLIERS)

SCEN = [
    ("actual", "Actual (Oct 2026)", "actual", lambda s: s),
    ("L1_cache", "Reuse prompt text like CMU's best group (same provider)", "local good", lambda s: raise_cache(s, OUTLIERS, LOCAL_CACHE)),
    ("L2_prompt", "Prompt size like CMU's best group", "local good", lambda s: trim_prompts(s, OUTLIERS)),
    ("L3_model_mix", "Frontier-model share like CMU's best group", "local good", lambda s: fix_model_mix(s, OUTLIERS)),
    ("L_all", "All three: match CMU's best group", "local good", L_all),
    ("G1_cache_step", f"Per unit: +{G_CACHE_STEP*100:.0f} points of reused prompt text, every team", "global good (per unit)",
     lambda s: raise_cache(s, ALL, plus=G_CACHE_STEP)),
    ("G2_route_step", f"Per unit: {G_ROUTE_STEP:.0%} of reasoning requests answered by gpt-4o instead", "global good (per unit)",
     lambda s: route_reasoning(s, G_ROUTE_STEP)),
]

# Data ceiling for routing (shown as "up to", never as a target): reasoning requests whose visible answer is no
# longer than the same tenant's median gpt-4o answer. Answer length is not task difficulty.
_o1 = s0[s0.model == REASONING].assign(v=lambda d: visible(d))
_g4med = s0[s0.model == REASONING_TO].assign(v=lambda d: visible(d)).groupby("tenant_id").v.median()
ROUTE_CEILING = (_o1.v <= _o1.tenant_id.map(_g4med)).mean()

rows = []
for sid, label, grp, fn in SCEN:
    r = totals(fn(s0))
    r.loc["ALL_CAMPUS"] = r.sum()
    r["scenario"], r["scenario_label"], r["group"] = sid, label, grp
    rows.append(r)
res = pd.concat(rows).reset_index().rename(columns={"index": "tenant_id"})
act = res[res.scenario == "actual"].set_index("tenant_id")
for col in ("cost_usd", "kwh_central", "kgco2e_central"):
    base = res.tenant_id.map(act[col])
    res[f"delta_{col}"] = res[col] - base
    res[f"delta_{col}_pct"] = (res[col] - base) / base * 100
labels = s0.groupby("tenant_id").persona_label.first()
labels["ALL_CAMPUS"] = "All campus"
res.insert(1, "persona_label", res.tenant_id.map(labels))

# L4: failed (400) calls avoided - reported separately, no $ / Wh attached (B0b X12)
err = pd.DataFrame({"pct_400_actual": pct400 * 100, "pct_400_local_good": PROVIDER_OF.map(LOCAL_400) * 100, "calls": calls_all})
err["failed_400_calls_avoided_30d"] = ((pct400 - PROVIDER_OF.map(LOCAL_400)).clip(lower=0) * calls_all).round().where(err.index.isin(OUTLIERS), 0)

out_dir = ROOT / "data-clean"
res.round(4).to_csv(out_dir / f"scenarios_by_tenant__{tag}.csv", index=False)
err.round(3).to_csv(out_dir / f"scenario_errors_avoided__{tag}.csv")

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(f"Pricing: {pricing_path.name}")
print(f"Local-good targets (best group on the same provider, D41): cache share {LOCAL_CACHE}; frontier share {LOCAL_FRONTIER}; 400 rate {LOCAL_400}")
print("Average baseline median prompt per model:\n", best_median.to_string())
print(f"Routing ceiling (data, not a target): {ROUTE_CEILING:.1%} of reasoning requests had answers <= same-tenant median gpt-4o answer")
pd.Series({"route_ceiling_share": ROUTE_CEILING}).to_csv(out_dir / "scenario_route_ceiling.csv", header=["value"])
view = res[["tenant_id", "scenario", "cost_usd", "delta_cost_usd_pct", "kwh_central", "delta_kwh_central_pct"]]
print("\n", view.pivot(index="scenario", columns="tenant_id", values="delta_cost_usd_pct").round(1).loc[[x[0] for x in SCEN]].to_string())
print("\nEnergy change % (central):\n", view.pivot(index="scenario", columns="tenant_id", values="delta_kwh_central_pct").round(1).loc[[x[0] for x in SCEN]].to_string())
camp = res[res.tenant_id == "ALL_CAMPUS"].set_index("scenario")[["cost_usd", "delta_cost_usd", "kwh_central", "delta_kwh_central", "delta_kgco2e_central"]]
print("\nCampus totals (30 days):\n", camp.round(1).to_string())
print("\n400s avoided:\n", err.to_string())
