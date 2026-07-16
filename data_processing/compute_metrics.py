"""Load the sample fact table, compute the metric pack, write it out."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fpa_toolkit import load, compute_metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "sample" / "financials_long.csv"
OUT = ROOT / "data" / "sample" / "metrics_long.csv"


def main() -> None:
    df = load(SRC)                    # reads through the one validated entry point
    metrics = compute_metrics(df)
    metrics.to_csv(OUT, index=False)
    print(f"wrote {len(metrics):,} metric rows to {OUT}")


if __name__ == "__main__":
    main()