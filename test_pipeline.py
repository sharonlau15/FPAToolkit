"""Tests for the FP&A pipeline.

These assert the financial invariants, not just that code runs — testing that the
balance sheet balances, the statements articulate, the drivers tie to the P&L, and
the price/volume/mix decomposition reconciles. Demonstrating that you *test the
financial logic* is itself a differentiator; most portfolio repos don't.
"""

import unittest

from fpa_toolkit import (
    Assumptions, generate_all, validate, validate_drivers, ContractError,
    compute_subtotals, compute_metrics, revenue_pvm_all,
)

CENT = 0.01


class PipelineInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.statements, cls.drivers = generate_all(Assumptions())

    def test_contract_validation_passes(self):
        # raises ContractError on any schema / balance / articulation violation
        validate(self.statements)
        validate_drivers(self.drivers, self.statements)

    def test_balance_sheet_balances(self):
        sub = compute_subtotals(self.statements)
        bs = sub[sub["account"].isin(["total_assets", "total_liab_and_equity"])]
        w = bs.pivot_table(index=["period", "scenario"], columns="account",
                           values="value")
        gap = (w["total_assets"] - w["total_liab_and_equity"]).abs().max()
        self.assertLessEqual(gap, CENT)

    def test_driver_revenue_ties_to_pl(self):
        d = self.drivers.pivot_table(
            index=["period", "scenario", "product"], columns="driver",
            values="value").reset_index()
        d["rev"] = d["units"] * d["unit_price"]
        drv_rev = d.groupby(["period", "scenario"])["rev"].sum()
        pl = self.statements[(self.statements.statement == "PL")
                             & (self.statements.account == "revenue")]
        pl_rev = pl.set_index(["period", "scenario"])["value"]
        gap = (drv_rev - pl_rev).abs().max()
        self.assertLessEqual(gap, CENT)

    def test_pvm_reconciles(self):
        pvm = revenue_pvm_all(self.drivers)  # raises AssertionError if it doesn't
        self.assertLessEqual(pvm["residual"].abs().max(), CENT)

    def test_activity_ratios_recover_assumptions(self):
        # DSO/DIO/DPO should invert the generator's inputs (55/85/60)
        m = compute_metrics(self.statements)
        for metric, expected in [("dso", 55.0), ("dio", 85.0), ("dpo", 60.0)]:
            vals = m[m.metric == metric]["value"]
            self.assertAlmostEqual(vals.min(), expected, places=6)
            self.assertAlmostEqual(vals.max(), expected, places=6)

    def test_validator_catches_broken_balance(self):
        bad = self.statements.copy()
        mask = ((bad.statement == "BS") & (bad.account == "cash")
                & (bad.period == "2022-06") & (bad.scenario == "actual"))
        bad.loc[mask, "value"] += 1_000_000  # unbalance one cell
        with self.assertRaises(ContractError):
            validate(bad)


if __name__ == "__main__":
    unittest.main()
