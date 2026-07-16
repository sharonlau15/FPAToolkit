"""Flux commentary: turn variances + PVM into the sentences an analyst writes.

Rule-based, not a language model — every sentence is traceable to a number, which
is the point in a finance context (an auditable comment beats a fluent guess).
The templates read material variances, order them by dollar impact, label
favorable/unfavorable, and attach the price/volume/mix story to the revenue line.
"""

from __future__ import annotations

import pandas as pd

from .variance import revenue_pvm, statement_variance

# human-readable labels for account keys
_LABELS = {
    "revenue": "Revenue", "cogs": "COGS", "gross_profit": "Gross profit",
    "opex_selling": "Selling expense", "opex_marketing": "Marketing expense",
    "opex_ga": "G&A expense", "depreciation": "Depreciation",
    "operating_income": "Operating income (EBIT)", "ebitda": "EBITDA",
    "interest_expense": "Interest expense", "pretax_income": "Pretax income",
    "tax_expense": "Tax expense", "net_income": "Net income",
}


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1_000_000:
        return f"{sign}${a/1_000_000:,.1f}M"
    if a >= 1_000:
        return f"{sign}${a/1_000:,.0f}k"
    return f"{sign}${a:,.0f}"


def _label(account: str) -> str:
    return _LABELS.get(account, account.replace("_", " ").capitalize())


def flux_commentary(statements: pd.DataFrame, drivers: pd.DataFrame, period: str, *,
                    base: str = "budget", actual: str = "actual",
                    abs_threshold: float = 100_000.0,
                    pct_threshold: float = 0.05,
                    top_n: int = 6) -> str:
    """Generate a management-style flux commentary for one period."""
    var = statement_variance(statements, base=base, actual=actual,
                             abs_threshold=abs_threshold, pct_threshold=pct_threshold)
    v = var[(var["period"] == period) & (var["statement"] == "PL")]

    lines: list[str] = [f"Flux commentary — {period} (actual vs {base})", ""]

    # headline: net income
    ni = v[v["account"] == "net_income"]
    if not ni.empty:
        r = ni.iloc[0]
        direction = "favorable" if r["favorable"] else "unfavorable"
        lines.append(
            f"Net income of {_money(r['actual'])} was {_money(abs(r['variance_abs']))} "
            f"{direction} to {base} ({r['variance_pct']*100:+.1f}%).")
        lines.append("")

    # revenue line with price/volume/mix
    rev = v[v["account"] == "revenue"]
    if not rev.empty:
        r = rev.iloc[0]
        pvm = revenue_pvm(drivers, period, base=base, actual=actual)
        direction = "favorable" if r["favorable"] else "unfavorable"
        drivers_txt = ", ".join(
            f"{name} {_money(pvm[key])}"
            for name, key in [("price", "price_effect"),
                              ("volume", "volume_effect"),
                              ("mix", "mix_effect")]
            if abs(pvm[key]) >= 1_000)
        lines.append(
            f"Revenue of {_money(r['actual'])} was {_money(abs(r['variance_abs']))} "
            f"{direction} to {base} ({r['variance_pct']*100:+.1f}%), decomposed into "
            f"{drivers_txt}.")

    # other material P&L lines, largest dollar impact first
    material = v[v["material"] & (v["account"] != "revenue")
                 & (v["account"] != "net_income")].copy()
    # keep the atomic/most-specific lines, drop redundant parent subtotals
    subtotals = {"gross_profit", "operating_income", "ebitda", "pretax_income"}
    material = material[~material["account"].isin(subtotals)]
    material["mag"] = material["variance_abs"].abs()
    material = material.sort_values("mag", ascending=False).head(top_n)

    if not material.empty:
        lines.append("")
        lines.append("Material drivers below the top line:")
        for _, r in material.iterrows():
            direction = "favorable" if r["favorable"] else "unfavorable"
            lines.append(
                f"  - {_label(r['account'])}: {_money(abs(r['variance_abs']))} "
                f"{direction} ({r['variance_pct']*100:+.1f}%).")

    return "\n".join(lines)
