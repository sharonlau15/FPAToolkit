# Data Contract

This is the single seam between *where data comes from* and *what the engine
does with it*. The generator (fake data) and any future real-data adapter both
promise to emit exactly this shape. The engine promises to consume exactly this
shape and nothing else. Neither side needs to know anything about the other.

## The fact table

One long/tidy table. Every financial number in the system is one row.

| column      | type   | meaning                                                        |
|-------------|--------|----------------------------------------------------------------|
| `period`    | string | Reporting month, `YYYY-MM` (month-end). e.g. `2024-01`         |
| `scenario`  | string | `actual` \| `budget` \| `forecast`                             |
| `statement` | string | `PL` \| `BS` \| `CF`                                            |
| `account`   | string | Canonical account key (see chart of accounts). e.g. `revenue` |
| `value`     | float  | Amount in reporting currency. Convention below.                |

Example rows:

```
period   scenario  statement  account               value
2024-01  budget    PL         revenue               5000000.00
2024-01  actual    PL         revenue               4925000.00
2024-01  actual    PL         cogs                  2085000.00
2024-01  actual    BS         accounts_receivable    742000.00
2024-01  actual    CF         cf_change_in_ar        -18000.00
```

## Sign convention (read this — it prevents 90% of downstream bugs)

Values are stored as **positive magnitudes** for P&L and Balance Sheet accounts.
Direction (does it add to or subtract from a subtotal) is **not** encoded in the
sign of `value` — it is a property of the account's *type*, defined once in the
chart of accounts. Roll-ups are computed as `Σ (sign(account_type) × value)`.

- `Revenue`   → magnitude positive, `+1` in P&L
- `Expense`   → magnitude positive, `-1` in P&L  (COGS is stored as `2085000`, not `-2085000`)
- `Asset`     → magnitude positive, `+1`
- `Liability` → magnitude positive, `+1` (within L&E)
- `Equity`    → magnitude positive, `+1` (within L&E)

Cash-flow accounts are the one exception: they are **stored signed** (uses of
cash negative, sources positive), because the same line flips direction month to
month. Their `account_type` is `CashFlow` and they roll up as a plain sum.

Rationale: this mirrors how enterprise FP&A systems (Hyperion / OneStream /
Anaplan) model accounts — account *type* carries sign behavior, the stored fact
is a clean magnitude. It means the engine never hard-codes `revenue - cogs`; it
sums members of a subtotal group using their type. Swap the chart of accounts,
the same engine still works.

## Subtotals are NOT stored

The table holds **atomic accounts only**. `gross_profit`, `ebit`, `net_income`,
`total_assets` etc. are *derived* by the engine from the chart-of-accounts
roll-up structure. Storing them would (a) duplicate truth and (b) let stored and
computed subtotals silently disagree. One source of truth: the atomic rows.

## Invariants the data must satisfy

Any conforming dataset — fake or real — must pass these (see `schema.validate`):

1. **Schema**: exactly the five columns, correct dtypes, no nulls, allowed
   values in `scenario` / `statement`, every `account` present in the chart of
   accounts.
2. **Balance sheet balances**, every period × scenario:
   `total_assets == total_liabilities + total_equity` (to the cent).
3. **Statements articulate**:
   - `CF.cf_net_income == PL.net_income`
   - `CF.net_change_in_cash == ΔBS.cash` (period over period)
   - `ΔBS.retained_earnings == PL.net_income − dividends`

If real data can't pass these, it isn't clean enough to report on — the contract
is also a data-quality gate, not just a shape.
