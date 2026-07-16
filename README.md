# FPAToolkit

## Data Generation
Data is fictitious and generated to provide numbers for the code to process. Run the CLI entry point from the repo root with:

```bash
pip install pandas numpy
python3 scripts/generate.py
```
1. DATA_CONTRACT.md — the seam. Five columns, long/tidy, documented sign convention. This is what makes "real data plugs in later" true instead of aspirational.
2. chart_of_accounts.py — the config that carries account structure as data. The engine never hard-codes revenue - cogs.
3. rollup.py — the config-driven engine core. It computes gross profit / EBIT / net income / total assets without naming a single account. Repoint it at a different chart of accounts and it still works. This is the "senior" signal.
4. generator.py — a real three-statement model. P&L from units × price × seasonality; working capital from DSO/DIO/DPO; cash derived from the indirect cash-flow statement. The BS balances as an accounting identity, not by luck.
5. schema.py — the contract as enforceable code. It doesn't just check column shapes; it asserts the BS balances and the CFS ties. Real data that can't pass this isn't clean enough to report on.

## Data Processing
1. loader,py -  the single validated entry point. Everything downstream reads through load(), so dtype coercion and contract-checking happen in exactly one place. This is the honest, thin version of "data processing" for a clean source; the heavy real-data adapter stays a later, separate piece.
2. metrics.py — 11 metrics (margins, cost ratios, DSO/DIO/DPO, CCC, YoY growth) as a registry. Each carries its unit and description so the report layer formats and labels without hardcoding. Add a metric = add a registry entry.
3. compute_metrics.py - Run it with python3 scripts/compute_metrics.py from the project root.

