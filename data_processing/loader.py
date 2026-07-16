"""The single entry point for getting data into the engine.

Every downstream module (metrics, variance, reporting) reads through `load` so
that (a) dtype coercion happens in exactly one place and (b) nothing computes on
data that hasn't passed the contract. The heavy transformation layer —
mapping a messy real-world export into the contract — is a separate adapter,
built later against a deliberately messy fixture, not here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import COLUMNS, validate

_DTYPES = {"period": str, "scenario": str, "statement": str, "account": str}


def load(path: str | Path, *, check: bool = True) -> pd.DataFrame:
    """Load a fact table from CSV, coerce dtypes, and (by default) validate it.

    Parameters
    ----------
    path : path to a CSV in the contract's long format.
    check : if True, run full contract validation (schema + balance + articulation)
            and raise ContractError on any violation. Turn off only for debugging.
    """
    df = pd.read_csv(path, dtype=_DTYPES)
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing required columns {missing}")
    df = df[COLUMNS].copy()
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    if check:
        validate(df)
    return df
