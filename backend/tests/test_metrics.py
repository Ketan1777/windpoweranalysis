import pandas as pd

from app.analytics.forecast_metrics import calculate_metrics


def test_calculate_metrics():
    actual = pd.Series([100, 200, 150])
    forecast = pd.Series([110, 180, 160])

    result = calculate_metrics(actual, forecast)

    assert result["sample_count"] == 3
    assert result["mae"] == 13.333
    assert result["rmse"] == 14.142
    assert result["bias"] == 0.0


def test_empty_data():
    result = calculate_metrics(
        pd.Series(dtype=float),
        pd.Series(dtype=float),
    )

    assert result["sample_count"] == 0
    assert result["mae"] is None
    assert result["rmse"] is None
    assert result["bias"] is None