"""Step 5a: cost per call / per tenant using a swappable pricing file.

Usage (from repo root):
    py scripts/03_cost.py                          # uses config/pricing_list.csv
    py scripts/03_cost.py config/pricing_cmu.csv   # swap in CMU rates later
Outputs: data-clean/calls_costed__<pricing>.csv, data-clean/cost_by_tenant__<pricing>.csv
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
pricing_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config" / "pricing_list.csv"
if not pricing_path.is_absolute():
    pricing_path = ROOT / pricing_path
tag = pricing_path.stem

price = pd.read_csv(pricing_path)
df = pd.read_csv(ROOT / "data-clean" / "calls_unified.csv")
missing = set(df["model"]) - set(price["model"])
if missing:
    sys.exit(f"Pricing file {pricing_path.name} is missing models: {missing}")

df = df.merge(price[["model", "usd_per_1m_input", "usd_per_1m_cached_input", "usd_per_1m_output", "status"]]
              .rename(columns={"status": "price_status"}), on="model", how="left")

ok = df["is_success"]
# Failed calls (400/429) are not billed by either provider and have no token counts -> cost 0, flagged.
df["cost_usd"] = 0.0
df.loc[ok, "cost_usd"] = (
    df.loc[ok, "uncached_input_tokens"] * df.loc[ok, "usd_per_1m_input"]
    + df.loc[ok, "cached_input_tokens"] * df.loc[ok, "usd_per_1m_cached_input"]
    + df.loc[ok, "output_tokens"] * df.loc[ok, "usd_per_1m_output"]
) / 1e6
# Counterfactual: what the same successful call would cost with zero caching
df["cost_usd_no_cache"] = 0.0
df.loc[ok, "cost_usd_no_cache"] = (
    df.loc[ok, "input_tokens"] * df.loc[ok, "usd_per_1m_input"]
    + df.loc[ok, "output_tokens"] * df.loc[ok, "usd_per_1m_output"]
) / 1e6
df["cache_savings_usd"] = df["cost_usd_no_cache"] - df["cost_usd"]

s = df[ok]
g = s.groupby(["tenant_id", "persona_label"])
by_tenant = pd.DataFrame({
    "successful_calls": g.size(),
    "total_cost_usd": g["cost_usd"].sum(),
    "cost_per_success_usd_mean": g["cost_usd"].mean(),
    "cost_per_success_usd_median": g["cost_usd"].median(),
    "cost_per_1k_tokens_usd": g["cost_usd"].sum() / g["total_tokens"].sum() * 1000,
    "cache_savings_usd": g["cache_savings_usd"].sum(),
    "cache_savings_pct": g["cache_savings_usd"].sum() / g["cost_usd_no_cache"].sum() * 100,
    "share_cost_unverified_price_pct": s[~s["price_status"].eq("verified-official")].groupby(["tenant_id", "persona_label"])["cost_usd"].sum()
                                         / g["cost_usd"].sum() * 100,
}).fillna(0)
by_tenant_model = s.groupby(["tenant_id", "model"])["cost_usd"].agg(["sum", "mean"]).round(4)

df.drop(columns=["usd_per_1m_input", "usd_per_1m_cached_input", "usd_per_1m_output"]) \
  .to_csv(ROOT / "data-clean" / f"calls_costed__{tag}.csv", index=False)
by_tenant.round(4).to_csv(ROOT / "data-clean" / f"cost_by_tenant__{tag}.csv")
by_tenant_model.to_csv(ROOT / "data-clean" / f"cost_by_tenant_model__{tag}.csv")

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(f"Pricing file: {pricing_path.name}")
print(by_tenant.round(4).to_string())
print("\nCost by tenant x model (sum, mean per call):\n", by_tenant_model.to_string())
print(f"\nTotal 30-day cost: ${s['cost_usd'].sum():,.2f} | cache savings: ${s['cache_savings_usd'].sum():,.2f}")
