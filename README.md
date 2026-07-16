# FP&A Reporting Toolkit

An automated financial planning & analysis pipeline: it takes financial statement
data, runs budget-vs-actual variance analysis, decomposes revenue variance into
**price / volume / mix**, computes the standard FP&A metric pack, and generates
management-style flux commentary — the work an analyst otherwise does by hand each
month.

The sample data is synthetic but **internally consistent**: the balance sheet
balances as an accounting identity, the cash flow statement ties the income
statement to the balance sheet, and operational drivers (units × price) reconcile
to reported revenue. That consistency is the point — the engine is built to run on
real data the moment it conforms to the contract.

> Note on tooling: this is deliberately built in Python (not the Power BI / Alteryx
> stack) for reproducibility, version control, and a zero-license, portable
> pipeline that runs the same on any machine.

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

That runs the full pipeline and writes all outputs to `data/sample/`. Useful flags:

```bash
python main.py --period 2023-09     # also print a flux commentary to the console
python main.py --stage generate     # run one stage: generate | metrics | variance
python main.py --outdir out          # choose the output directory
```

Run the tests (they assert the financial invariants, not just that code runs):

```bash
python -m pytest tests/            # or: python -m unittest discover tests
```

## How it fits together

```
        generate ─▶ validate ─▶ metrics ─▶ variance ─▶ PVM ─▶ flux commentary
           │           │
     drivers table   data contract (schema + articulation + driver tie-out)
```

Everything flows through one data contract, so no stage computes on unvalidated
data. See `docs/DATA_CONTRACT.md` for the seam that makes real-data swap-in real.

## Package layout

- `fpa_toolkit/chart_of_accounts.py` — account structure as *config*: statement,
  type (sign behaviour), roll-up membership, and variance polarity. The engine
  never hard-codes `revenue - cogs`.
- `fpa_toolkit/rollup.py` — config-driven roll-up: computes gross profit / EBIT /
  net income / total assets from atomic rows without naming a single account.
  Repoint it at a different chart of accounts and it still works.
- `fpa_toolkit/generator.py` — a driver-based three-statement model. Revenue is
  the sum of per-product (units × price) streams; working capital is driven by
  DSO/DIO/DPO; cash is derived from the indirect cash-flow statement, so the
  balance sheet balances by construction.
- `fpa_toolkit/schema.py` — the data contract as enforceable code: schema shape,
  balance-sheet balancing, statement articulation, and the driver revenue tie-out.
- `fpa_toolkit/loader.py` — the single validated entry point for getting data in.
- `fpa_toolkit/metrics.py` — margins, cost ratios, DSO/DIO/DPO, cash conversion
  cycle, and YoY growth as a registry (add a metric = add an entry).
- `fpa_toolkit/variance.py` — budget-vs-actual variance with favorable/unfavorable
  labelling and materiality gating, plus the reconciling price/volume/mix
  decomposition of revenue.
- `fpa_toolkit/commentary.py` — rule-based flux commentary; every sentence is
  traceable to a number (auditable, not a language-model guess).

## Outputs (`data/sample/`)

`financials_long.csv`, `drivers_long.csv` (source facts) · `*_wide.csv` (human
views) · `metrics_long.csv` · `variance_long.csv` · `revenue_pvm.csv` ·
`flux_commentary_examples.txt`.
