"""Synthetic three-statement + driver generator that ARTICULATES by construction.

This is a small driver-based financial model, not random numbers.

  drivers (units x price, per product)  ->  revenue
  revenue  ->  COGS / opex  ->  P&L
  activity ratios (DSO/DIO/DPO)  ->  working capital
  indirect cash-flow statement  ->  cash

Because cash is the CFS plug and retained earnings roll with net income, the
balance sheet balances as an accounting identity, not by luck. And because total
revenue is built as the SUM of per-product streams, the operational drivers tie
to the P&L exactly (sum of units x price == revenue) -- which is what makes a
genuine price / volume / mix decomposition possible downstream.

Two scenarios from the SAME model:
  - budget : the clean plan.
  - actual : the plan perturbed by structured, explainable variances:
      * pricing action        (+price on all products)          -> price effect
      * mid-year volume dip    (units soft, all products)        -> volume effect
      * premium trade-down     (premium units down, core up)     -> mix effect
      * H2 input-cost inflation (COGS % up)                      -> margin
      * one-off legal charge, Q4 marketing overspend             -> opex flux

Deterministic given a seed, so the repo reproduces identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

STATEMENT_COLUMNS = ["period", "scenario", "statement", "account", "value"]
DRIVER_COLUMNS = ["period", "scenario", "product", "driver", "value"]


# ------------------------------------------------------------------------------
# Products. Total base ~ $5.1M/month (~$61M/yr). Three tiers at different price
# points so mix is a real, decomposable effect.
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Product:
    key: str
    base_units: float
    base_price: float
    annual_growth: float


DEFAULT_PRODUCTS: tuple[Product, ...] = (
    Product("core",    600_000, 4.00, 0.04),   # value line: high vol, low price
    Product("plus",    300_000, 6.00, 0.06),
    Product("premium", 100_000, 9.00, 0.08),   # premium: low vol, high price
)


@dataclass(frozen=True)
class Assumptions:
    start_period: str = "2022-01"
    n_months: int = 36
    seed: int = 42

    products: tuple[Product, ...] = DEFAULT_PRODUCTS
    # seasonal index by calendar month (Jan..Dec), mean ~1.0. Consumer-health
    # shape: stronger cold/flu season (Q4-Q1), softer summer. Shared across products.
    seasonality: tuple = (1.15, 1.12, 1.05, 0.98, 0.92, 0.88,
                          0.85, 0.90, 0.98, 1.05, 1.10, 1.02)

    # --- margins & cost structure ---
    gross_margin: float = 0.58                  # -> COGS = revenue * (1 - gm)
    selling_pct_of_rev: float = 0.11            # variable
    marketing_pct_of_rev: float = 0.09          # variable
    ga_fixed_monthly: float = 1_100_000.0       # fixed, grows slowly
    ga_annual_growth: float = 0.03
    tax_rate: float = 0.24

    # --- capital / balance sheet ---
    dso_days: float = 55.0
    dio_days: float = 85.0
    dpo_days: float = 60.0
    capex_pct_of_rev: float = 0.03
    dep_annual_rate: float = 0.10               # ~10yr straight-line on gross PP&E
    debt_paydown_monthly: float = 60_000.0
    dividend_payout: float = 0.30               # of net income, paid quarterly

    # --- opening balance sheet (cash set as opening plug so it starts balanced) ---
    open_ppe_net: float = 14_000_000.0
    open_debt: float = 10_000_000.0
    open_common_stock: float = 8_000_000.0
    open_retained_earnings: float = 6_000_000.0
    interest_rate_annual: float = 0.06


@dataclass(frozen=True)
class ActualVariances:
    """Structured deltas applied to 'actual' vs the 'budget' plan. Each maps to a
    sentence a real FP&A analyst would write in a flux commentary."""
    # revenue-side (drive price / volume / mix effects)
    price_realization: float = 0.015            # +1.5% pricing action, all products
    volume_soft_months: tuple = (5, 6, 7)       # 0-indexed: mid-year softness
    volume_soft_pct: float = -0.04              # -4% units in those months, all products
    mix_shift_start: int = 12                   # sustained mix shift from here
    premium_vol_delta: float = -0.08            # premium demand weakness
    core_vol_delta: float = 0.03                # trade-down into the value line
    # cost-side (statement level)
    h2_cogs_inflation: float = 0.012            # +1.2pt COGS as % rev from month 18
    h2_start_month: int = 18
    legal_charge_month: int = 20                # one-off G&A hit
    legal_charge_amount: float = 900_000.0
    q4_marketing_overspend_months: tuple = (9, 10, 11, 21, 22, 23)
    q4_marketing_overspend: float = 250_000.0


def _periods(start: str, n: int) -> list[str]:
    return [str(p) for p in pd.period_range(start=start, periods=n, freq="M")]


def _product_drivers(a: Assumptions, var: ActualVariances | None,
                     scenario: str, t: int, seas: float) -> dict[str, tuple[float, float]]:
    """Return {product_key: (units, unit_price)} for month t under the scenario."""
    out = {}
    for p in a.products:
        units = p.base_units * (1 + p.annual_growth) ** (t / 12.0) * seas
        price = p.base_price
        if scenario == "actual" and var is not None:
            price *= (1 + var.price_realization)
            if t in var.volume_soft_months:
                units *= (1 + var.volume_soft_pct)
            if t >= var.mix_shift_start:
                if p.key == "premium":
                    units *= (1 + var.premium_vol_delta)
                elif p.key == "core":
                    units *= (1 + var.core_vol_delta)
        out[p.key] = (units, price)
    return out


def _generate_scenario(a: Assumptions, scenario: str,
                       var: ActualVariances | None):
    """Build one scenario's monthly series. Returns (statement_rows, driver_rows)."""
    periods = _periods(a.start_period, a.n_months)
    rows: list[dict] = []
    drows: list[dict] = []

    ppe = a.open_ppe_net
    debt = a.open_debt
    retained = a.open_retained_earnings
    common = a.open_common_stock
    cash = None
    prev = {"ar": 0.0, "inv": 0.0, "ap": 0.0, "debt": debt}
    start_month_num = int(a.start_period[5:7])

    for t, period in enumerate(periods):
        seas = a.seasonality[(start_month_num - 1 + t) % 12]

        # --- revenue built up from product drivers ---
        drivers = _product_drivers(a, var, scenario, t, seas)
        revenue = 0.0
        for prod_key, (units, price) in drivers.items():
            revenue += units * price
            drows.append({"period": period, "scenario": scenario,
                          "product": prod_key, "driver": "units", "value": float(units)})
            drows.append({"period": period, "scenario": scenario,
                          "product": prod_key, "driver": "unit_price", "value": float(price)})

        # --- COGS / gross margin ---
        cogs_pct = 1 - a.gross_margin
        if (scenario == "actual" and var is not None and t >= var.h2_start_month):
            cogs_pct += var.h2_cogs_inflation
        cogs = revenue * cogs_pct

        # --- opex ---
        selling = revenue * a.selling_pct_of_rev
        marketing = revenue * a.marketing_pct_of_rev
        ga = a.ga_fixed_monthly * (1 + a.ga_annual_growth) ** (t / 12.0)
        if scenario == "actual" and var is not None:
            if t in var.q4_marketing_overspend_months:
                marketing += var.q4_marketing_overspend
            if t == var.legal_charge_month:
                ga += var.legal_charge_amount

        # --- depreciation, interest, tax ---
        depreciation = ppe * a.dep_annual_rate / 12.0
        interest = prev["debt"] * a.interest_rate_annual / 12.0
        ebit = revenue - cogs - selling - marketing - ga - depreciation
        pretax = ebit - interest
        tax = max(pretax, 0.0) * a.tax_rate
        net_income = pretax - tax

        # --- working capital (activity ratios) ---
        ar_new = revenue * 12 * a.dso_days / 365.0
        inv_new = cogs * 12 * a.dio_days / 365.0
        ap_new = cogs * 12 * a.dpo_days / 365.0

        # --- capex / PP&E ---
        capex = revenue * a.capex_pct_of_rev
        ppe_new = ppe + capex - depreciation

        # --- financing ---
        debt_new = max(debt - a.debt_paydown_monthly, 0.0)
        dividends = net_income * a.dividend_payout if (t % 3 == 2 and net_income > 0) else 0.0

        # --- opening cash plug (month 0): make opening BS balance ---
        if cash is None:
            open_assets_excl_cash = prev["ar"] + prev["inv"] + a.open_ppe_net
            open_le = prev["ap"] + a.open_debt + common + retained
            cash = open_le - open_assets_excl_cash

        # --- indirect cash flow -> ending cash ---
        d_ar = ar_new - prev["ar"]
        d_inv = inv_new - prev["inv"]
        d_ap = ap_new - prev["ap"]
        d_debt = debt_new - prev["debt"]
        cf_operating = net_income + depreciation - d_ar - d_inv + d_ap
        cf_investing = -capex
        cf_financing = d_debt - dividends
        cash_new = cash + cf_operating + cf_investing + cf_financing
        retained_new = retained + net_income - dividends

        def add(statement, account, value):
            rows.append({"period": period, "scenario": scenario, "statement": statement,
                         "account": account, "value": float(value)})

        add("PL", "revenue", revenue)
        add("PL", "cogs", cogs)
        add("PL", "opex_selling", selling)
        add("PL", "opex_marketing", marketing)
        add("PL", "opex_ga", ga)
        add("PL", "depreciation", depreciation)
        add("PL", "interest_expense", interest)
        add("PL", "tax_expense", tax)

        add("BS", "cash", cash_new)
        add("BS", "accounts_receivable", ar_new)
        add("BS", "inventory", inv_new)
        add("BS", "ppe_net", ppe_new)
        add("BS", "accounts_payable", ap_new)
        add("BS", "debt", debt_new)
        add("BS", "common_stock", common)
        add("BS", "retained_earnings", retained_new)

        add("CF", "cf_net_income", net_income)
        add("CF", "cf_depreciation", depreciation)
        add("CF", "cf_change_in_ar", -d_ar)
        add("CF", "cf_change_in_inventory", -d_inv)
        add("CF", "cf_change_in_ap", d_ap)
        add("CF", "cf_capex", -capex)
        add("CF", "cf_change_in_debt", d_debt)
        add("CF", "cf_dividends", -dividends)

        ppe, debt, retained, cash = ppe_new, debt_new, retained_new, cash_new
        prev = {"ar": ar_new, "inv": inv_new, "ap": ap_new, "debt": debt_new}

    return rows, drows


def generate_all(assumptions: Assumptions | None = None,
                 variances: ActualVariances | None = None):
    """Generate (statements, drivers), both conforming to their contracts."""
    a = assumptions or Assumptions()
    v = variances or ActualVariances()
    np.random.seed(a.seed)
    b_rows, b_dr = _generate_scenario(a, "budget", var=None)
    a_rows, a_dr = _generate_scenario(a, "actual", var=v)
    statements = pd.DataFrame(b_rows + a_rows)[STATEMENT_COLUMNS]
    drivers = pd.DataFrame(b_dr + a_dr)[DRIVER_COLUMNS]
    return statements, drivers


def generate(assumptions: Assumptions | None = None,
             variances: ActualVariances | None = None) -> pd.DataFrame:
    """Statements only (back-compatible)."""
    return generate_all(assumptions, variances)[0]


def generate_drivers(assumptions: Assumptions | None = None,
                     variances: ActualVariances | None = None) -> pd.DataFrame:
    """Driver table only."""
    return generate_all(assumptions, variances)[1]
