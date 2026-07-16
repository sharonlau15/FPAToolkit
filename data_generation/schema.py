"""The data contract, as enforceable code.

DATA_CONTRACT.md is the human-readable version; this is the machine-checkable
one. Both the generator and any future real-data adapter must produce a frame
that passes `validate()`.
"""

from __future__ import annotations

import re

import pandas as pd

from .chart_of_accounts import SUBTOTALS, all_account_keys
from .rollup import compute_subtotals

COLUMNS = ["period", "scenario", "statement", "account", "value"]
SCENARIOS = {"actual", "budget", "forecast"}
STATEMENTS = {"PL", "BS", "CF"}
_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")

# tolerance for float equality on money, in currency units (one cent)
CENT = 0.01


class ContractError(ValueError):
    """Raised when a dataframe violates the data contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a fact table against the contract. Returns df unchanged on success,
    raises ContractError on the first violation found."""
    _validate_schema(df)
    _validate_balance_sheet(df)
    _validate_articulation(df)
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    _require(list(df.columns) == COLUMNS,
             f"columns must be exactly {COLUMNS}, got {list(df.columns)}")
    _require(df["period"].map(lambda p: bool(_PERIOD_RE.match(str(p)))).all(),
             "every period must match YYYY-MM")
    bad_scen = set(df["scenario"]) - SCENARIOS
    _require(not bad_scen, f"unknown scenario(s): {bad_scen}")
    bad_stmt = set(df["statement"]) - STATEMENTS
    _require(not bad_stmt, f"unknown statement(s): {bad_stmt}")
    bad_acct = set(df["account"]) - all_account_keys()
    _require(not bad_acct, f"account(s) not in chart of accounts: {bad_acct}")
    _require(df["value"].notna().all(), "value column contains nulls")
    _require(pd.api.types.is_numeric_dtype(df["value"]), "value must be numeric")
    dupes = df.duplicated(["period", "scenario", "statement", "account"])
    _require(not dupes.any(),
             f"duplicate (period,scenario,statement,account) rows: {int(dupes.sum())}")


def _validate_balance_sheet(df: pd.DataFrame) -> None:
    sub = compute_subtotals(df)
    bs = sub[(sub["statement"] == "BS")
             & sub["account"].isin(["total_assets", "total_liab_and_equity"])]
    wide = bs.pivot_table(index=["period", "scenario"], columns="account",
                          values="value")
    gap = (wide["total_assets"] - wide["total_liab_and_equity"]).abs()
    worst = gap.max()
    _require(worst <= CENT,
             f"balance sheet does not balance; worst A-(L+E) gap = {worst:.4f} "
             f"at {gap.idxmax()}")


def _validate_articulation(df: pd.DataFrame) -> None:
    sub = compute_subtotals(df)

    def series(statement: str, account: str) -> pd.Series:
        s = sub[(sub["statement"] == statement) & (sub["account"] == account)]
        return s.set_index(["scenario", "period"])["value"].sort_index()

    # CF.cf_net_income == PL.net_income
    ni_pl = series("PL", "net_income")
    ni_cf = series("CF", "cf_net_income")
    gap = (ni_pl - ni_cf).abs().max()
    _require(gap <= CENT, f"CF net income != PL net income; worst gap {gap:.4f}")

    # CF.net_change_in_cash == period-over-period delta in BS.cash
    ncc = series("CF", "net_change_in_cash")
    cash = series("BS", "cash")
    dcash = cash.groupby(level="scenario").diff()
    joined = pd.concat({"ncc": ncc, "dcash": dcash}, axis=1).dropna()
    gap = (joined["ncc"] - joined["dcash"]).abs().max()
    _require(pd.isna(gap) or gap <= CENT,
             f"net change in cash != delta cash; worst gap {gap:.4f}")
