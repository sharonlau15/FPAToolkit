"""Financial metrics, computed off the rolled-up statements.

Same design stance as the rest of the repo: metrics live in a registry, not in
a wall of procedural code. Each entry carries its formula, its unit (so the report
layer formats % / days / x correctly without guessing), and a plain-language
description. Adding a metric is adding a registry entry.

CONVENTION — activity ratios (DSO/DIO/DPO):
    We annualise the period's flow (monthly revenue or COGS x 12) and divide the
    period-end balance by average daily flow. On the sample data this recovers the
    generator's input assumptions exactly (DSO 55, DIO 85, DPO 60), which is the
    point: the metric inverts the generator cleanly. The industry-standard
    alternative is a trailing-12-month flow basis; swap `_annualise` to change it.
    Note this deliberately does not smooth seasonality — a period-end AR balance
    tracking recent sales is realistic; constant credit terms => constant DSO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .rollup import compute_subtotals

_ANNUALISE = 12.0  # monthly flow -> annual flow
_DAYS = 365.0


@dataclass(frozen=True)
class Metric:
    key: str
    fn: Callable[[pd.DataFrame], pd.Series]  # takes wide frame -> series
    unit: str  # 'pct' | 'days' | 'x' | 'ratio'
    description: str


def _wide(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot atomic + subtotal rows to one row per (period, scenario), columns =
    account/subtotal names. Metrics are then simple column arithmetic."""
    sub = compute_subtotals(df)
    w = sub.pivot_table(index=["period", "scenario"], columns="account",
                        values="value")
    return w.sort_index()


def _dso(w):
    return w["accounts_receivable"] / (w["revenue"] * _ANNUALISE) * _DAYS


def _dio(w):
    return w["inventory"] / (w["cogs"] * _ANNUALISE) * _DAYS


def _dpo(w):
    return w["accounts_payable"] / (w["cogs"] * _ANNUALISE) * _DAYS


def _ccc(w):
    return _dso(w) + _dio(w) - _dpo(w)


def _rev_growth_yoy(w):
    # 12-period lag within each scenario; NaN for the first year (documented).
    rev = w["revenue"]
    lagged = rev.groupby(level="scenario").shift(12)
    return rev / lagged - 1


METRIC_REGISTRY: dict[str, Metric] = {m.key: m for m in [
    Metric("gross_margin",   lambda w: w["gross_profit"] / w["revenue"],
           "pct", "Gross profit as a % of revenue."),
    Metric("ebit_margin",    lambda w: w["operating_income"] / w["revenue"],
           "pct", "Operating income (EBIT) as a % of revenue."),
    Metric("net_margin",     lambda w: w["net_income"] / w["revenue"],
           "pct", "Net income as a % of revenue."),
    Metric("selling_ratio",  lambda w: w["opex_selling"] / w["revenue"],
           "pct", "Selling expense as a % of revenue."),
    Metric("marketing_ratio",lambda w: w["opex_marketing"] / w["revenue"],
           "pct", "Marketing expense as a % of revenue."),
    Metric("ga_ratio",       lambda w: w["opex_ga"] / w["revenue"],
           "pct", "G&A expense as a % of revenue."),
    Metric("dso", _dso, "days", "Days sales outstanding (AR collection period)."),
    Metric("dio", _dio, "days", "Days inventory outstanding (inventory holding period)."),
    Metric("dpo", _dpo, "days", "Days payable outstanding (supplier payment period)."),
    Metric("ccc", _ccc, "days", "Cash conversion cycle = DSO + DIO - DPO."),
    Metric("rev_growth_yoy", _rev_growth_yoy, "pct",
           "Year-over-year revenue growth (NaN for first 12 months)."),
]}


def compute_metrics(df: pd.DataFrame,
                    metrics: list[str] | None = None) -> pd.DataFrame:
    """Return a tidy long frame: metric | period | scenario | value | unit.

    Long format on purpose — it composes with everything else (variance can run
    on metrics, the report layer can pivot as needed), same as the fact table.
    """
    w = _wide(df)
    keys = metrics or list(METRIC_REGISTRY)
    out = []
    for k in keys:
        m = METRIC_REGISTRY[k]
        s = m.fn(w).rename("value").reset_index()
        s["metric"] = m.key
        s["unit"] = m.unit
        out.append(s[["metric", "period", "scenario", "value", "unit"]])
    return pd.concat(out, ignore_index=True).sort_values(
        ["metric", "scenario", "period"]).reset_index(drop=True)
