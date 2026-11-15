"""Step 2b: are there real differences among the 4 'look-alike' tenants?

Same-provider pairs only (so model families match):
  OpenAI : org-prod-core       vs org-marketing-ai
  Gemini : prj-ai-enterprise-prod vs prj-ai-r-and-d
With ~30k calls per tenant almost any gap is 'statistically significant', so we report
effect size + 95% CI and flag PRACTICAL relevance (|relative diff| >= 10%).
Run from repo root: py scripts/04_small_differences.py -> data-clean/small_differences.csv
"""
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
pricing_tag = sys.argv[1] if len(sys.argv) > 1 else "pricing_list"
df = pd.read_csv(ROOT / "data-clean" / f"calls_costed__{pricing_tag}.csv")
rng = np.random.default_rng(42)
PAIRS = [("org-prod-core", "org-marketing-ai"), ("prj-ai-enterprise-prod", "prj-ai-r-and-d")]
PRACTICAL = 10.0  # % relative difference considered meaningful for a campus audience
rows = []


def two_prop(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se else 0
    pval = math.erfc(abs(z) / math.sqrt(2))
    se_d = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return p1 * 100, p2 * 100, (p1 - p2 - 1.96 * se_d) * 100, (p1 - p2 + 1.96 * se_d) * 100, pval


def boot_diff(a, b, stat, n=2000):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = [stat(rng.choice(a, a.size)) - stat(rng.choice(b, b.size)) for _ in range(n)]
    return stat(a), stat(b), np.percentile(d, 2.5), np.percentile(d, 97.5)


def ratio_of_sums(cols):
    return lambda idx_arr: idx_arr[:, 0].sum() / idx_arr[:, 1].sum()


def add(pair, scope, metric, va, vb, lo, hi, pval=None):
    rel = (va - vb) / vb * 100 if vb else float("nan")
    excludes0 = not (lo <= 0 <= hi)
    rows.append(dict(pair=f"{pair[0]} vs {pair[1]}", scope=scope, metric=metric,
                     a=round(va, 4), b=round(vb, 4), rel_diff_pct=round(rel, 1),
                     ci95_low=round(lo, 4), ci95_high=round(hi, 4),
                     p_value=None if pval is None else f"{pval:.2g}",
                     statistically_clear=excludes0,
                     practically_meaningful=bool(excludes0 and abs(rel) >= PRACTICAL)))


for pair in PAIRS:
    A, B = (df[df.tenant_id == t] for t in pair)
    # error rates (all calls)
    for code in (400, 429):
        pa, pb, lo, hi, p = two_prop((A.status_code == code).sum(), len(A), (B.status_code == code).sum(), len(B))
        add(pair, "all models", f"% calls HTTP {code}", pa, pb, lo, hi, p)
    sA, sB = A[A.is_success], B[B.is_success]
    # model mix
    for m in sorted(set(sA.model)):
        pa, pb, lo, hi, p = two_prop((sA.model == m).sum(), len(sA), (sB.model == m).sum(), len(sB))
        add(pair, m, "% of successful calls on this model", pa, pb, lo, hi, p)
    # per-model token + cache + cost metrics
    for m in sorted(set(sA.model)):
        a, b = sA[sA.model == m], sB[sB.model == m]
        for col, lab in (("input_tokens", "median input tokens"), ("output_tokens", "median output tokens"),
                         ("cost_usd", "median cost per successful call (USD)")):
            va, vb, lo, hi = boot_diff(a[col], b[col], np.median)
            add(pair, m, lab, va, vb, lo, hi)
        va, vb, lo, hi = boot_diff(a.input_tokens, b.input_tokens, lambda x: np.percentile(x, 90))
        add(pair, m, "p90 input tokens", va, vb, lo, hi)
        pa, pb, lo, hi, p = two_prop((a.cached_input_tokens > 0).sum(), len(a), (b.cached_input_tokens > 0).sum(), len(b))
        add(pair, m, "% calls with any cache hit", pa, pb, lo, hi, p)
        ca, cb = a[a.cached_input_tokens > 0], b[b.cached_input_tokens > 0]
        va, vb, lo, hi = boot_diff(ca.cache_hit_share * 100, cb.cache_hit_share * 100, np.median)
        add(pair, m, "median cache share when cache is used (%)", va, vb, lo, hi)
        if m == "o1-preview":
            ra, rb = a.reasoning_tokens / a.output_tokens * 100, b.reasoning_tokens / b.output_tokens * 100
            va, vb, lo, hi = boot_diff(ra, rb, np.median)
            add(pair, m, "median reasoning share of output (%)", va, vb, lo, hi)
    # mean cost per successful call, all models
    va, vb, lo, hi = boot_diff(sA.cost_usd, sB.cost_usd, np.mean)
    add(pair, "all models", "mean cost per successful call (USD)", va, vb, lo, hi)

out = pd.DataFrame(rows)
out.to_csv(ROOT / "data-clean" / "small_differences.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 45)
print(out.drop(columns=["p_value"]).to_string(index=False))
print("\nPRACTICALLY MEANINGFUL (CI excludes 0 and |rel diff| >= 10%):")
print(out[out.practically_meaningful][["pair", "scope", "metric", "a", "b", "rel_diff_pct"]].to_string(index=False))
