"""Step 5b: ESTIMATED energy (Wh) and carbon (gCO2e) per call, as a low / central / high range.

Method (user decision D14):
 1. For each benchmark model in config/energy_benchmarks.csv, solve E = a + b_in*input + b_out*output
    exactly from Jegham et al.'s 3 prompt sizes (short/medium/long) -> per-token energy coefficients.
 2. Map each telemetry model to a benchmark (config/carbon_params.csv; Gemini + o1-preview are PROXIES).
 3. Per successful call:  E_high = a + b_in*(uncached + cached*share_high) + b_out*output
                          E_low  = low_energy_scale * (a + b_in*(uncached + cached*share_low) + b_out*output)
                          E_central = midpoint of low and high
 4. Carbon = energy x grid factor (low grid with low energy, central with central, high with high).
 5. Caching "avoided" energy = energy if cached tokens were billed as normal input minus actual.
Failed calls (400/429) get 0 (no token data) - flagged as a limitation.
ALL VALUES ARE ESTIMATES FROM PUBLISHED BENCHMARKS, NOT MEASUREMENTS. Data is synthetic.

Run from repo root: py scripts/06_carbon.py [pricing_tag]
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
pricing_tag = sys.argv[1] if len(sys.argv) > 1 else "pricing_list"
bench = pd.read_csv(ROOT / "config" / "energy_benchmarks.csv")
params = pd.read_csv(ROOT / "config" / "carbon_params.csv").set_index("param")["value"]
P = lambda k: float(params[k])

# 1. exact 3-point solve per benchmark model
SIZES = np.array([[1, 100, 300], [1, 1000, 1000], [1, 10000, 1500]], float)
coef = {}
for _, r in bench.iterrows():
    a, b_in, b_out = np.linalg.solve(SIZES, [r.short_wh, r.medium_wh, r.long_wh])
    coef[r.benchmark_model] = (a, b_in, b_out)
print("Per-call energy coefficients (Wh): a = fixed per call, b_in / b_out per token")
for k, (a, bi, bo) in coef.items():
    print(f"  {k:12s} a={a:.4f}  b_in={bi*1000:.4f} Wh/1K in  b_out={bo*1000:.4f} Wh/1K out")

model_map = {k.split(":", 1)[1]: v for k, v in params.items() if k.startswith("model_map:")}

df = pd.read_csv(ROOT / "data-clean" / f"calls_costed__{pricing_tag}.csv")
ok = df["is_success"]
c = np.array([coef[model_map[m]] for m in df["model"]])
a, bi, bo = c[:, 0], c[:, 1], c[:, 2]
unc = df["uncached_input_tokens"].fillna(0).to_numpy()
cac = df["cached_input_tokens"].fillna(0).to_numpy()
out = df["output_tokens"].fillna(0).to_numpy()
okm = ok.to_numpy()

def energy(cache_share, scale):
    return np.where(okm, scale * (a + bi * (unc + cac * cache_share) + bo * out), 0.0)

s = P("low_energy_scale")
df["wh_high"] = energy(P("cached_input_energy_share_high"), 1.0)
df["wh_low"] = energy(P("cached_input_energy_share_low"), s)
df["wh_central"] = (df["wh_low"] + df["wh_high"]) / 2
# no-cache counterfactual (cached tokens treated as normal input)
df["wh_nocache_high"] = energy(1.0, 1.0)
df["wh_nocache_low"] = energy(1.0, s)
df["wh_nocache_central"] = (df["wh_nocache_low"] + df["wh_nocache_high"]) / 2
for lvl in ("low", "central", "high"):
    df[f"gco2e_{lvl}"] = df[f"wh_{lvl}"] / 1000 * P(f"grid_g_per_kwh_{lvl}")
df["benchmark_proxy"] = df["model"].map(model_map)
df["energy_is_proxy"] = df["model"].isin(["o1-preview", "gemini-1.5-pro", "gemini-1.5-flash"])

df.to_csv(ROOT / "data-clean" / f"calls_costed_carbon__{pricing_tag}.csv", index=False)

sc = df[ok]
g = sc.groupby(["tenant_id", "persona_label"])
t = pd.DataFrame({
    "calls": g.size(),
    "wh_per_call_low": g.wh_low.mean(), "wh_per_call_central": g.wh_central.mean(), "wh_per_call_high": g.wh_high.mean(),
    "kwh_30d_low": g.wh_low.sum() / 1000, "kwh_30d_central": g.wh_central.sum() / 1000, "kwh_30d_high": g.wh_high.sum() / 1000,
    "kgco2e_30d_low": g.gco2e_low.sum() / 1000, "kgco2e_30d_central": g.gco2e_central.sum() / 1000, "kgco2e_30d_high": g.gco2e_high.sum() / 1000,
    "wh_per_1k_tokens_central": g.wh_central.sum() / g.total_tokens.sum() * 1000,
    "cache_avoided_kwh_central": (g.wh_nocache_central.sum() - g.wh_central.sum()) / 1000,
    "cache_avoided_pct_central": (g.wh_nocache_central.sum() - g.wh_central.sum()) / g.wh_nocache_central.sum() * 100,
    "share_energy_from_proxy_models_pct": sc[sc.energy_is_proxy].groupby(["tenant_id", "persona_label"]).wh_central.sum() / g.wh_central.sum() * 100,
}).fillna(0)
t.round(4).to_csv(ROOT / "data-clean" / f"carbon_by_tenant__{pricing_tag}.csv")
tm = sc.groupby(["tenant_id", "model"]).agg(wh_mean_central=("wh_central", "mean"), kwh_central=("wh_central", lambda x: x.sum() / 1000))
tm["share_of_tenant_energy_pct"] = tm.kwh_central / tm.groupby(level=0).kwh_central.transform("sum") * 100
tm.round(3).to_csv(ROOT / "data-clean" / f"carbon_by_tenant_model__{pricing_tag}.csv")

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 20)
print("\n", t.round(3).to_string())
print("\nBy tenant x model:\n", tm.round(3).to_string())
tot = {l: sc[f"wh_{l}"].sum() / 1000 for l in ("low", "central", "high")}
co2 = {l: sc[f"gco2e_{l}"].sum() / 1000 for l in ("low", "central", "high")}
print(f"\n30-day total energy kWh: low {tot['low']:.1f} | central {tot['central']:.1f} | high {tot['high']:.1f}")
print(f"30-day total kgCO2e:     low {co2['low']:.1f} | central {co2['central']:.1f} | high {co2['high']:.1f}")
