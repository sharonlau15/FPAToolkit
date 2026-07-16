"""Chart of accounts: the config that makes the engine account-set-agnostic.

Everything about *how numbers roll up* lives here as data, not as code buried in
the engine. Point the engine at a different chart of accounts (e.g. a real ERP's)
and the same computation logic still produces correct statements.

Two structures:

- ACCOUNTS: every atomic account -> its statement, type, and display order.
  The `type` carries sign behaviour for roll-ups (see DATA_CONTRACT.md).
- SUBTOTALS: derived lines -> the ordered list of member accounts/subtotals that
  compose them. The engine walks this to compute gross_profit, ebit, net_income,
  total_assets, etc. Members may be atomic accounts or other subtotals, so the
  structure nests (net_income is built from ebit which is built from gross_profit...).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- account types and their sign behaviour in a roll-up -----------------------
# sign = multiplier applied to the (positive-magnitude) stored value when summing
# into a subtotal. CashFlow values are already signed, so their multiplier is +1.
ACCOUNT_TYPE_SIGN: dict[str, int] = {
    "Revenue": +1,
    "Expense": -1,
    "Asset": +1,
    "Liability": +1,
    "Equity": +1,
    "CashFlow": +1,
}


@dataclass(frozen=True)
class Account:
    key: str
    statement: str  # PL | BS | CF
    type: str  # one of ACCOUNT_TYPE_SIGN
    order: int  # display order within its statement


# --- atomic accounts (the only things stored in the fact table) ----------------
ACCOUNTS: dict[str, Account] = {a.key: a for a in [
    # ---- P&L ----
    Account("revenue",          "PL", "Revenue", 10),
    Account("cogs",             "PL", "Expense", 20),
    Account("opex_selling",     "PL", "Expense", 40),
    Account("opex_marketing",   "PL", "Expense", 50),
    Account("opex_ga",          "PL", "Expense", 60),
    Account("depreciation",     "PL", "Expense", 70),
    Account("interest_expense", "PL", "Expense", 90),
    Account("tax_expense",      "PL", "Expense", 110),
    # ---- Balance sheet ----
    Account("cash",                "BS", "Asset",     10),
    Account("accounts_receivable", "BS", "Asset",     20),
    Account("inventory",           "BS", "Asset",     30),
    Account("ppe_net",             "BS", "Asset",     40),
    Account("accounts_payable",    "BS", "Liability", 60),
    Account("debt",                "BS", "Liability", 70),
    Account("common_stock",        "BS", "Equity",    90),
    Account("retained_earnings",   "BS", "Equity",   100),
    # ---- Cash flow (stored signed) ----
    Account("cf_net_income",         "CF", "CashFlow", 10),
    Account("cf_depreciation",       "CF", "CashFlow", 20),
    Account("cf_change_in_ar",       "CF", "CashFlow", 30),
    Account("cf_change_in_inventory","CF", "CashFlow", 40),
    Account("cf_change_in_ap",       "CF", "CashFlow", 50),
    Account("cf_capex",              "CF", "CashFlow", 70),
    Account("cf_change_in_debt",     "CF", "CashFlow", 90),
    Account("cf_dividends",          "CF", "CashFlow", 100),
]}


# --- derived subtotals (computed by the engine, never stored) ------------------
# order matters: later subtotals may reference earlier ones.
SUBTOTALS: dict[str, list[str]] = {
    # P&L
    "gross_profit":     ["revenue", "cogs"],
    "operating_income": ["gross_profit", "opex_selling", "opex_marketing",
                         "opex_ga", "depreciation"],  # EBIT
    "ebitda":           ["operating_income", "depreciation"],  # add D&A back
    "pretax_income":    ["operating_income", "interest_expense"],
    "net_income":       ["pretax_income", "tax_expense"],
    # Balance sheet
    "current_assets":       ["cash", "accounts_receivable", "inventory"],
    "total_assets":         ["current_assets", "ppe_net"],
    "total_liabilities":    ["accounts_payable", "debt"],
    "total_equity":         ["common_stock", "retained_earnings"],
    "total_liab_and_equity":["total_liabilities", "total_equity"],
    # Cash flow
    "cf_operating": ["cf_net_income", "cf_depreciation", "cf_change_in_ar",
                     "cf_change_in_inventory", "cf_change_in_ap"],
    "cf_investing": ["cf_capex"],
    "cf_financing": ["cf_change_in_debt", "cf_dividends"],
    "net_change_in_cash": ["cf_operating", "cf_investing", "cf_financing"],
}


def sign_of(account_key: str) -> int:
    """Roll-up multiplier for an atomic account, from its type."""
    return ACCOUNT_TYPE_SIGN[ACCOUNTS[account_key].type]


def all_account_keys() -> set[str]:
    return set(ACCOUNTS)
