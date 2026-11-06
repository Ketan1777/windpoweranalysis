import math
import pandas as pd


def calculate_metrics(
    actual: pd.Series,
    forecast: pd.Series
) -> dict:
    """
    Calculate forecast accuracy metrics.

    Error = Forecast - Actual
    MAE   = Mean Absolute Error
    RMSE  = Root Mean Squared Error
    Bias  = Mean Forecast Error
    """

    actual = pd.to_numeric(actual, errors="coerce")
    forecast = pd.to_numeric(forecast, errors="coerce")

    # Keep only pairs with valid numeric values.
    data = pd.DataFrame({
        "actual": actual,
        "forecast": forecast
    }).dropna()

    if data.empty:
        return {
            "sample_count": 0,
            "mae": None,
            "rmse": None,
            "bias": None
        }

    errors = data["forecast"] - data["actual"]

    mae = errors.abs().mean()
    rmse = math.sqrt((errors ** 2).mean())
    bias = errors.mean()

    return {
        "sample_count": len(data),
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "bias": round(float(bias), 3)
    }