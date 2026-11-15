# Pricing config (swappable)

`scripts/03_cost.py` reads per-model prices from a CSV. Default: `config/pricing_list.csv` (published list prices).

**To swap in CMU AI Gateway rates later:** copy `pricing_list.csv` to `pricing_cmu.csv`, edit the three price columns (keep the same `model` names), set `status`/`source`, then run:

```
py scripts/03_cost.py config/pricing_cmu.csv
```

Outputs are written with the pricing file's name as a suffix (e.g. `data-clean/cost_by_tenant__pricing_cmu.csv`), so both versions can sit side by side.

Column meanings (USD per 1 million tokens):
- `usd_per_1m_input` – uncached input (prompt) tokens
- `usd_per_1m_cached_input` – input tokens served from the prompt/context cache
- `usd_per_1m_output` – output tokens (OpenAI reasoning tokens are already counted inside output)

Not modeled: Gemini context-cache **storage** fees (per token-hour; the logs don't record cache lifetime), batch/flex discounts, and >128k-token tiers (max prompt in data = 52,188).
