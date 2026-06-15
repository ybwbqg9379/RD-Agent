"""[FORK] Export RD-Agent / qlib predictions to the cross-repo *signals* contract.

Why this exists
---------------
The three sibling forks are decoupled at the code level (none imports another); they
coordinate through **artifacts**, not Python imports. This module defines and writes
the one artifact that bridges the research factory and the trading desk:

    RD-Agent (evolve factor/model)  ──signals.parquet──▶  TradingAgents (decide/trade)

See ``~/AI-STACK.md`` → "三仓库协作" for the big picture.

The contract (schema v1)
------------------------
A single tidy/long parquet file, one row per (date, ticker):

    column   dtype             meaning
    ------   ---------------   ---------------------------------------------------
    date     datetime64[ns]    trading day (naive, midnight) the score is *for*
    ticker   string            instrument symbol, upper-case (e.g. "AAPL")
    score    float64           model/factor signal; higher == more bullish

Rows are sorted by (date, score desc). Alongside ``<name>.parquet`` we write a
``<name>.meta.json`` sidecar describing provenance (source, model, row/date/ticker
counts) so the consumer can sanity-check what it is reading. TradingAgents only needs
to ``pd.read_parquet`` and filter by date — no qlib dependency.

Producing the input
-------------------
qlib's ``SignalRecord`` saves ``pred.pkl`` (a DataFrame with a ``score`` column and a
MultiIndex ``(datetime, instrument)``) under its mlflow recorder dir. Point this script
at that pickle::

    python -m rdagent.custom.export_signals \
        --pred path/to/pred.pkl --out signals/lgb_alpha158_us.parquet

Programmatic use::

    from rdagent.custom.export_signals import export_signals, normalize_signals
    df = normalize_signals(pred_df)          # pure: Series/DataFrame -> canonical df
    export_signals("pred.pkl", "signals/x.parquet", model="lightgbm_alpha158_us")
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = 1
COLUMNS = ["date", "ticker", "score"]


def normalize_signals(obj: pd.Series | pd.DataFrame, score_col: str | None = None) -> pd.DataFrame:
    """Coerce a qlib prediction object into the canonical ``[date, ticker, score]`` frame.

    Accepts the common qlib ``SignalRecord`` shapes:
      * a ``Series`` with a 2-level (datetime, instrument) MultiIndex, or
      * a ``DataFrame`` with that index and a score column (named ``score`` by default,
        else the single column, else ``score_col``).

    Pure (no I/O) so the normalization is unit-testable offline.
    """
    if isinstance(obj, pd.Series):
        df = obj.rename("score").to_frame()
    elif isinstance(obj, pd.DataFrame):
        if score_col is not None:
            col = score_col
        elif "score" in obj.columns:
            col = "score"
        elif obj.shape[1] == 1:
            col = obj.columns[0]
        else:
            raise ValueError(
                f"Ambiguous score column in DataFrame with columns {list(obj.columns)}; "
                "pass score_col=...",
            )
        df = obj[[col]].rename(columns={col: "score"})
    else:
        raise TypeError(f"Expected pandas Series or DataFrame, got {type(obj).__name__}")

    if not isinstance(df.index, pd.MultiIndex) or df.index.nlevels != 2:
        raise ValueError("Expected a 2-level (datetime, instrument) MultiIndex on the prediction.")

    out = df.reset_index()
    out.columns = ["date", "ticker", "score"]
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["ticker"] = out["ticker"].astype("string").str.upper()
    out["score"] = pd.to_numeric(out["score"], errors="coerce").astype("float64")
    out = out.dropna(subset=["score"])
    out = out.sort_values(["date", "score"], ascending=[True, False]).reset_index(drop=True)
    return out[COLUMNS]


def _meta(df: pd.DataFrame, source: str | None, model: str | None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "columns": COLUMNS,
        "rows": len(df),
        "n_tickers": int(df["ticker"].nunique()),
        "date_min": df["date"].min().date().isoformat() if len(df) else None,
        "date_max": df["date"].max().date().isoformat() if len(df) else None,
        "model": model,
        "source": source,
        "generated_by": "rdagent.custom.export_signals",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def export_signals(
    pred: str | Path,
    out: str | Path,
    model: str | None = None,
    score_col: str | None = None,
) -> Path:
    """Read a qlib prediction pickle, normalize it, and write ``out`` (parquet) + sidecar.

    Returns the parquet path. Writes ``<out stem>.meta.json`` next to it.
    """
    pred_path = Path(pred).expanduser()
    raw = pd.read_pickle(pred_path)
    df = normalize_signals(raw, score_col=score_col)

    out_path = Path(out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(_meta(df, source=str(pred_path), model=model), indent=2))
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="[FORK] Export qlib/RD-Agent predictions to the signals.parquet contract.",
    )
    p.add_argument("--pred", required=True, help="qlib prediction pickle (SignalRecord pred.pkl).")
    p.add_argument("--out", required=True, help="Output .parquet path (a .meta.json sidecar is written too).")
    p.add_argument("--model", default=None, help="Optional model name recorded in the sidecar.")
    p.add_argument("--score-col", default=None, help="Score column name if the DataFrame is ambiguous.")
    args = p.parse_args(argv)

    out_path = export_signals(args.pred, args.out, model=args.model, score_col=args.score_col)
    meta = json.loads(out_path.with_suffix(".meta.json").read_text())
    print(f"wrote {out_path}  ({meta['rows']} rows, {meta['n_tickers']} tickers, "
          f"{meta['date_min']}..{meta['date_max']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
