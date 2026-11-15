"""Step 2 (first pass): per-tenant efficiency summary, normalized per call.
No cost/carbon yet - those need external pricing + energy benchmarks (plan step 4/5).
Run from repo root: py scripts/02_tenant_summary.py  ->  data-clean/tenant_summary.csv
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data-clean" / "calls_unified.csv", parse_dates=["ts_utc"])
s = df[df["is_success"]]

g = df.groupby(["tenant_id", "persona_label", "provider", "merge_candidate"])
summary = pd.DataFrame({
    "calls": g.size(),
    "pct_400": g["status_code"].apply(lambda x: (x == 400).mean() * 100),
    "pct_429": g["status_code"].apply(lambda x: (x == 429).mean() * 100),
})
gs = s.groupby("tenant_id")
summary = summary.reset_index().set_index("tenant_id")
summary["median_input_tok"] = gs["input_tokens"].median()
summary["p90_input_tok"] = gs["input_tokens"].quantile(0.9)
summary["median_output_tok"] = gs["output_tokens"].median()
summary["cache_share_tokenweighted_pct"] = gs["cached_input_tokens"].sum() / gs["input_tokens"].sum() * 100
summary["pct_calls_zero_cache"] = gs["cached_input_tokens"].apply(lambda x: (x == 0).mean() * 100)
summary["total_tokens_M"] = gs["total_tokens"].sum() / 1e6

mix = (s.groupby(["tenant_id", "model"]).size() / gs.size() * 100).unstack().round(1)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(summary.round(1).to_string())
print("\nModel mix (% of successful calls):\n", mix.fillna(0).to_string())

print("\nMedian input tokens by tenant x model:\n",
      s.groupby(["tenant_id", "model"])["input_tokens"].median().unstack().to_string())

o1 = s[s["model"] == "o1-preview"]
print("\no1-preview reasoning share of output (median):",
      (o1["reasoning_tokens"] / o1["output_tokens"]).median().round(3))

# Retry-storm check: are 429s clustered in time?
df["minute"] = df["ts_utc"].dt.floor("min")
per_min = df[df["status_code"] == 429].groupby(["tenant_id", "minute"]).size()
print("\n429s per (tenant, minute): max", per_min.max(), "| share of 429-minutes with >=3:",
      round((per_min >= 3).mean() * 100, 2), "%")
daily = df.groupby(["date"])["status_code"].apply(lambda x: (x == 429).mean() * 100)
print("Daily 429 % range:", round(daily.min(), 2), "-", round(daily.max(), 2))
wk = df.groupby("weekday").size()
print("Calls by weekday:", wk.to_dict())

summary.round(2).to_csv(ROOT / "data-clean" / "tenant_summary.csv")
