"""Variance analysis: actual vs budget, with favorable/unfavorable labelling,
materiality gating, and a reconciling price / volume / mix decomposition on revenue.

STATEMENT VARIANCE
    For any account or subtotal: absolute variance (actual - budget), percent
    variance, and a favorable/unfavorable label derived from the account's polarity
    (revenue up = favorable; cost up = unfavorable). Materiality is a two-part gate
    -- an absolute floor AND a percent floor -- so we neither flag a large % on a
    trivial account nor a large $ on an immaterial-% one.

PRICE / VOLUME / MIX (PVM)
    Revenue variance is decomposed against operational drivers. Convention (stated
    explicitly, because PVM conventions differ and naming yours is the mark of
    knowing the analysis):

        price_effect  = sum_i  Q^A_i * (P^A_i - P^B_i)
        volume_effect = (sum_i Q^A_i - sum_i Q^B_i) * avg_budget_price
        mix_effect    = sum_i (Q^A_i - sum_i Q^A * budget_share_i) * P^B_i

    where A = actual, B = budget, Q = units, P = unit price, budget_share_i =
    Q^B_i / sum_i Q^B_i, and avg_budget_price = sum_i Q^B_i P^B_i / sum_i Q^B_i.

    These three effects sum to the total revenue variance exactly (proven by
    construction; the module asserts reconciliation to the cent). Price uses the
    actual quantity so the volume/mix split carries no residual interaction term.
"""

from __future__ import annotations

import pandas as pd

from .chart_of_accounts import polarity
from .rollup import compute_subtotals

CENT = 0.01


def statement_variance(statements: pd.DataFrame, *,
                       base: str = "budget", actual: str = "actual",
                       abs_threshold: float = 100_000.0,
                       pct_threshold: float = 0.05) -> pd.DataFrame:
    """Return per (account, period) variance of `actual` vs `base`.

    Columns: statement, account, period, actual, base, variance_abs,
             variance_pct, favorable, material.
    Includes derived subtotals (net_income, gross_profit, ...), not just atomics.
    """
    sub = compute_subtotals(statements)
    wide = sub.pivot_table(index=["statement", "account", "period"],
                           columns="scenario", values="value")
    if base not in wide or actual not in wide:
        raise ValueError(f"need scenarios '{base}' and '{actual}' in the data")
    out = wide[[actual, base]].rename(columns={actual: "actual", base: "base"}).reset_index()
    out["variance_abs"] = out["actual"] - out["base"]
    out["variance_pct"] = out["variance_abs"] / out["base"].replace(0, pd.NA)

    def _favorable(row):
        pol = polarity(row["account"])
        if pol is None:
            return pd.NA
        # higher-is-better -> positive variance favorable; else the reverse
        return (row["variance_abs"] > 0) == pol

    out["favorable"] = out.apply(_favorable, axis=1)
    out["material"] = ((out["variance_abs"].abs() >= abs_threshold)
                       & (out["variance_pct"].abs() >= pct_threshold))
    return out.sort_values(["statement", "account", "period"]).reset_index(drop=True)


def _drivers_wide(drivers: pd.DataFrame, scenario: str, period: str) -> pd.DataFrame:
    d = drivers[(drivers["scenario"] == scenario) & (drivers["period"] == period)]
    w = d.pivot_table(index="product", columns="driver", values="value")
    return w[["units", "unit_price"]]


def revenue_pvm(drivers: pd.DataFrame, period: str, *,
                base: str = "budget", actual: str = "actual") -> dict:
    """Decompose one period's revenue variance into price / volume / mix effects.

    Returns a dict with the three effects, the total variance, and the
    reconciliation residual (which is ~0 by construction)."""
    a = _drivers_wide(drivers, actual, period)
    b = _drivers_wide(drivers, base, period)
    idx = a.index.union(b.index)
    a = a.reindex(idx).fillna(0.0)
    b = b.reindex(idx).fillna(0.0)

    qa, pa = a["units"], a["unit_price"]
    qb, pb = b["units"], b["unit_price"]

    qa_tot, qb_tot = qa.sum(), qb.sum()
    rev_a = float((qa * pa).sum())
    rev_b = float((qb * pb).sum())
    avg_budget_price = (qb * pb).sum() / qb_tot if qb_tot else 0.0
    budget_share = qb / qb_tot if qb_tot else qb * 0.0

    price_effect = float((qa * (pa - pb)).sum())
    volume_effect = float((qa_tot - qb_tot) * avg_budget_price)
    mix_effect = float(((qa - qa_tot * budget_share) * pb).sum())

    total = rev_a - rev_b
    residual = total - (price_effect + volume_effect + mix_effect)
    return {
        "period": period,
        "revenue_actual": rev_a,
        "revenue_budget": rev_b,
        "total_variance": total,
        "price_effect": price_effect,
        "volume_effect": volume_effect,
        "mix_effect": mix_effect,
        "residual": residual,
    }


def revenue_pvm_all(drivers: pd.DataFrame, *,
                    base: str = "budget", actual: str = "actual") -> pd.DataFrame:
    """PVM for every period. Asserts each period reconciles to the cent."""
    periods = sorted(drivers["period"].unique())
    rows = [revenue_pvm(drivers, p, base=base, actual=actual) for p in periods]
    out = pd.DataFrame(rows)
    worst = out["residual"].abs().max()
    if worst > CENT:
        raise AssertionError(f"PVM does not reconcile; worst residual {worst:.4f}")
    return out
