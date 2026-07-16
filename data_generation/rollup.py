"""Roll-up engine: derive subtotals from atomic rows using the chart of accounts.

This is the piece that proves the config-driven design pays off. It never
mentions 'revenue' or 'cogs' by name. It walks SUBTOTALS, applies each atomic
account's type sign, and produces gross_profit / ebit / net_income / total_assets
/ etc. Repoint it at a different chart of accounts and it still works.
"""

from __future__ import annotations

import pandas as pd

from .chart_of_accounts import ACCOUNTS, SUBTOTALS, sign_of

_KEY = ["period", "scenario", "statement"]


def _statement_of_subtotal(members: list[str]) -> str:
    """A subtotal lives on the same statement as its members."""
    for m in members:
        if m in ACCOUNTS:
            return ACCOUNTS[m].statement
    # member is itself a subtotal -> recurse
    return _statement_of_subtotal(SUBTOTALS[m])


def compute_subtotals(df: pd.DataFrame) -> pd.DataFrame:
    """Return the atomic rows plus all derived subtotal rows, stacked.

    Signed value for an atomic account = sign(type) * value. Subtotals are the
    signed sum of their members. Because members can be other subtotals, we
    evaluate in insertion order (SUBTOTALS is ordered so dependencies come first).
    """
    # signed magnitude per atomic account
    atomic = df.copy()
    atomic["signed"] = [sign_of(a) * v for a, v in zip(df["account"], df["value"])]

    # running store of computed signed series, keyed by account/subtotal name,
    # each indexed by (period, scenario)
    signed: dict[str, pd.Series] = {}
    for key, g in atomic.groupby("account"):
        signed[key] = g.set_index(["period", "scenario"])["signed"]

    out_rows = [df]  # keep original atomic rows (positive magnitudes) as-is
    for name, members in SUBTOTALS.items():
        total = None
        for m in members:
            s = signed[m]
            total = s if total is None else total.add(s, fill_value=0.0)
        signed[name] = total
        stmt = _statement_of_subtotal(members)
        sub_df = total.reset_index()
        sub_df.columns = ["period", "scenario", "value"]
        sub_df["statement"] = stmt
        sub_df["account"] = name
        out_rows.append(sub_df[["period", "scenario", "statement", "account", "value"]])

    return pd.concat(out_rows, ignore_index=True)
