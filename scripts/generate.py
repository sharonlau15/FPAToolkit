#!/usr/bin/env python3
"""CLI entry point for generating the synthetic financial statement dataset."""

from __future__ import annotations

import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_generation.generator import Assumptions, ActualVariances, generate
from data_generation.schema import validate


def main() -> int:
    output_dir = Path(os.environ.get("OUTPUT_DIR", REPO_ROOT))
    output_dir.mkdir(parents=True, exist_ok=True)

    df = generate(Assumptions(), ActualVariances())
    validate(df)

    output_path = output_dir / "generated_data.csv"
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
