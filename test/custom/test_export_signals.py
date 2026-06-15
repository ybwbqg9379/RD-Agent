"""[FORK] Offline tests for the signals.parquet contract normalizer."""

import json

import pandas as pd
import pytest

from rdagent.custom.export_signals import COLUMNS, SCHEMA_VERSION, export_signals, normalize_signals


def _pred_df() -> pd.DataFrame:
    # qlib SignalRecord shape: ('datetime','instrument') MultiIndex + a 'score' column.
    idx = pd.MultiIndex.from_tuples(
        [
            ("2024-01-02", "aapl"),
            ("2024-01-02", "msft"),
            ("2024-01-03", "aapl"),
        ],
        names=["datetime", "instrument"],
    )
    return pd.DataFrame({"score": [0.1, 0.5, -0.2]}, index=idx)


@pytest.mark.offline
def test_normalize_from_dataframe_and_series():
    df = normalize_signals(_pred_df())
    assert list(df.columns) == COLUMNS
    # upper-cased tickers, datetime dates, float scores
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert str(df["date"].dtype).startswith("datetime64")
    # within a date, sorted by score descending: MSFT(0.5) before AAPL(0.1)
    first_day = df[df["date"] == pd.Timestamp("2024-01-02")]
    assert list(first_day["ticker"]) == ["MSFT", "AAPL"]

    # a bare Series (no 'score' column) normalizes identically
    s = _pred_df()["score"]
    assert normalize_signals(s).equals(df)


@pytest.mark.offline
def test_normalize_rejects_bad_shapes():
    with pytest.raises(ValueError):  # flat index, not 2-level
        normalize_signals(pd.Series([1.0, 2.0]))
    with pytest.raises(ValueError):  # ambiguous: >1 column and none named 'score'
        df = _pred_df().rename(columns={"score": "pred"}).assign(extra=1.0)
        normalize_signals(df)
    with pytest.raises(TypeError):
        normalize_signals([1, 2, 3])  # type: ignore[arg-type]


@pytest.mark.offline
def test_export_writes_parquet_and_sidecar(tmp_path):
    pred = tmp_path / "pred.pkl"
    _pred_df().to_pickle(pred)
    out = tmp_path / "sig" / "signals.parquet"

    written = export_signals(pred, out, model="lightgbm_alpha158_us")
    assert written == out and out.exists()

    back = pd.read_parquet(out)
    assert list(back.columns) == COLUMNS and len(back) == 3

    meta = json.loads(out.with_suffix(".meta.json").read_text())
    assert meta["schema_version"] == SCHEMA_VERSION
    assert meta["rows"] == 3 and meta["n_tickers"] == 2
    assert meta["model"] == "lightgbm_alpha158_us"
    assert meta["date_min"] == "2024-01-02" and meta["date_max"] == "2024-01-03"
