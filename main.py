"""FP&A Toolkit — single entry point that runs the whole pipeline.

    generate -> validate -> metrics -> variance -> PVM -> flux commentary

Every stage reads through the data contract, so nothing computes on data that
hasn't passed validation. The console output surfaces the two tie-outs that make
this repo credible: the balance sheet balances, and the price/volume/mix
decomposition reconciles to the revenue variance.

Usage:
    python main.py                      # run everything, write to ./data/sample
    python main.py --outdir out         # choose output directory
    python main.py --period 2023-09     # also print a flux commentary to console
    python main.py --stage generate     # run a single stage (generate|metrics|variance)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fpa_toolkit import (
    Assumptions, generate_all, validate, validate_drivers,
    compute_subtotals, load, compute_metrics,
    statement_variance, revenue_pvm_all, flux_commentary,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "data" / "sample"

# periods with the richest stories, used for the committed commentary examples
EXAMPLE_PERIODS = ["2023-09", "2022-06", "2024-12"]


def _banner(msg: str) -> None:
    print(f"\n{'─' * 4} {msg} {'─' * (60 - len(msg))}")


def stage_generate(outdir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    _banner("generate + validate")
    statements, drivers = generate_all(Assumptions())
    validate(statements)                       # schema + balance + articulation
    validate_drivers(drivers, statements)      # driver shape + revenue tie-out

    outdir.mkdir(parents=True, exist_ok=True)
    statements.to_csv(outdir / "financials_long.csv", index=False)
    drivers.to_csv(outdir / "drivers_long.csv", index=False)

    sub = compute_subtotals(statements)
    for stmt, name in [("PL", "income_statement"), ("BS", "balance_sheet"),
                       ("CF", "cash_flow")]:
        (sub[sub["statement"] == stmt]
         .pivot_table(index=["statement", "account"],
                      columns=["scenario", "period"], values="value")
         .to_csv(outdir / f"{name}_wide.csv"))

    # report the balance-sheet tie-out explicitly
    bs = sub[sub["account"].isin(["total_assets", "total_liab_and_equity"])]
    w = bs.pivot_table(index=["period", "scenario"], columns="account", values="value")
    worst = (w["total_assets"] - w["total_liab_and_equity"]).abs().max()
    print(f"  statements: {len(statements):,} rows   drivers: {len(drivers):,} rows")
    print(f"  balance sheet balances — worst A-(L+E) gap: ${worst:,.4f}")
    return statements, drivers


def stage_metrics(outdir: Path) -> pd.DataFrame:
    _banner("metrics")
    df = load(outdir / "financials_long.csv")
    metrics = compute_metrics(df)
    metrics.to_csv(outdir / "metrics_long.csv", index=False)
    n = metrics["metric"].nunique()
    print(f"  {n} metrics × {metrics['period'].nunique()} periods × "
          f"{metrics['scenario'].nunique()} scenarios → {len(metrics):,} rows")
    return metrics


def stage_variance(outdir: Path, commentary_period: str | None) -> pd.DataFrame:
    _banner("variance + PVM + commentary")
    df = load(outdir / "financials_long.csv")
    drivers = pd.read_csv(outdir / "drivers_long.csv", dtype={"period": str})

    statement_variance(df).to_csv(outdir / "variance_long.csv", index=False)
    pvm = revenue_pvm_all(drivers)             # asserts reconciliation to the cent
    pvm.to_csv(outdir / "revenue_pvm.csv", index=False)

    text = "\n\n".join(flux_commentary(df, drivers, p) for p in EXAMPLE_PERIODS)
    (outdir / "flux_commentary_examples.txt").write_text(text)

    print(f"  PVM reconciles across all periods — worst residual: "
          f"${pvm['residual'].abs().max():,.4f}")
    print(f"  wrote variance_long.csv, revenue_pvm.csv, flux_commentary_examples.txt")

    if commentary_period:
        _banner(f"flux commentary — {commentary_period}")
        print(flux_commentary(df, drivers, commentary_period))
    return pvm


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the FP&A reporting pipeline.")
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUT,
                    help="output directory (default: data/sample)")
    ap.add_argument("--period", type=str, default=None,
                    help="print a flux commentary for this period, e.g. 2023-09")
    ap.add_argument("--stage", choices=["generate", "metrics", "variance", "all"],
                    default="all", help="run a single stage (default: all)")
    args = ap.parse_args()

    if args.stage in ("generate", "all"):
        stage_generate(args.outdir)
    if args.stage in ("metrics", "all"):
        stage_metrics(args.outdir)
    if args.stage in ("variance", "all"):
        stage_variance(args.outdir, args.period)

    _banner("done")
    print(f"  outputs in {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
