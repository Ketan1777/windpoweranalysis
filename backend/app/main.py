from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.forecast_metrics import calculate_metrics
from app.services.elexon_service import (
    fetch_wind_actuals,
    fetch_wind_forecasts,
)


app = FastAPI(
    title="Wind Forecast Analytics API",
    description=(
        "Analyze UK wind generation forecasts against actual "
        "generation using Elexon data."
    ),
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://windpoweranalysis.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UK_TIMEZONE = ZoneInfo("Europe/London")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "Wind Forecast Analytics API",
    }


@app.get("/api/wind/analysis")
async def wind_analysis(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 1, 31)),
):
    """
    Analyze January 2026 purchasing decisions.

    Each purchasing decision relates to electricity delivery
    on the following day.

    Forecast selection:
    Select the latest forecast published before midnight
    (Europe/London) at the beginning of the delivery day.
    """

    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )

    # Purchasing decisions must fall within January 2026.
    if (
        start_date < date(2026, 1, 1)
        or end_date > date(2026, 1, 31)
    ):
        raise HTTPException(
            status_code=400,
            detail="Decision dates must be within January 2026.",
        )

    # Delivery happens one day after the purchasing decision.
    delivery_start_date = start_date + timedelta(days=1)
    delivery_end_date = end_date + timedelta(days=1)

    # Convert UK local delivery-date boundaries to UTC.
    start = pd.Timestamp(
        datetime.combine(delivery_start_date, time.min),
        tz=UK_TIMEZONE,
    ).tz_convert("UTC")

    end = pd.Timestamp(
        datetime.combine(
            delivery_end_date + timedelta(days=1),
            time.min,
        ),
        tz=UK_TIMEZONE,
    ).tz_convert("UTC")

    period = {
        "decision_start_date": str(start_date),
        "decision_end_date": str(end_date),
        "delivery_start_date": str(delivery_start_date),
        "delivery_end_date": str(delivery_end_date),
    }

    try:
        # Fetch Elexon data.
        actual_records = await fetch_wind_actuals()
        forecast_records = await fetch_wind_forecasts()

        actual_df = pd.DataFrame(actual_records)
        forecast_df = pd.DataFrame(forecast_records)

        # Validate API response fields.
        required_actual = {
            "startTime",
            "generation",
        }

        required_forecast = {
            "startTime",
            "publishTime",
            "generation",
        }

        if not required_actual.issubset(actual_df.columns):
            raise ValueError(
                "Actual dataset is missing required fields. "
                f"Received: {list(actual_df.columns)}"
            )

        if not required_forecast.issubset(forecast_df.columns):
            raise ValueError(
                "Forecast dataset is missing required fields. "
                f"Received: {list(forecast_df.columns)}"
            )

        # Convert timestamps to UTC.
        actual_df["startTime"] = pd.to_datetime(
            actual_df["startTime"],
            utc=True,
            errors="coerce",
        )

        forecast_df["startTime"] = pd.to_datetime(
            forecast_df["startTime"],
            utc=True,
            errors="coerce",
        )

        forecast_df["publishTime"] = pd.to_datetime(
            forecast_df["publishTime"],
            utc=True,
            errors="coerce",
        )

        # Convert generation values to numeric.
        actual_df["generation"] = pd.to_numeric(
            actual_df["generation"],
            errors="coerce",
        )

        forecast_df["generation"] = pd.to_numeric(
            forecast_df["generation"],
            errors="coerce",
        )

        # Filter actual generation by delivery period.
        actual_df = actual_df[
            (actual_df["startTime"] >= start)
            & (actual_df["startTime"] < end)
        ].dropna(
            subset=["startTime", "generation"]
        )

        # Filter forecasts by delivery period.
        forecast_df = forecast_df[
            (forecast_df["startTime"] >= start)
            & (forecast_df["startTime"] < end)
        ].dropna(
            subset=[
                "startTime",
                "publishTime",
                "generation",
            ]
        )

        if actual_df.empty or forecast_df.empty:
            return {
                "period": period,
                "metrics": calculate_metrics(
                    pd.Series(dtype=float),
                    pd.Series(dtype=float),
                ),
                "records": [],
                "record_count": 0,
                "message": (
                    "No matching actual and forecast data "
                    "was returned for this period."
                ),
            }

        # Remove duplicate actual records by averaging
        # generation values for the same target period.
        actual_df = (
            actual_df.groupby(
                "startTime",
                as_index=False,
            )["generation"]
            .mean()
            .rename(
                columns={
                    "generation": "actualGeneration"
                }
            )
        )

        # Determine the delivery date in UK local time.
        delivery_dates = (
            forecast_df["startTime"]
            .dt.tz_convert(UK_TIMEZONE)
            .dt.date
        )

        # Calculate midnight UK time for each delivery date.
        forecast_df["decisionCutoff"] = [
            pd.Timestamp(
                datetime.combine(delivery_date, time.min),
                tz=UK_TIMEZONE,
            ).tz_convert("UTC")
            for delivery_date in delivery_dates
        ]

        # Only forecasts published before the delivery-day
        # cutoff are eligible.
        eligible_forecasts = forecast_df[
            forecast_df["publishTime"]
            < forecast_df["decisionCutoff"]
        ].copy()

        excluded_forecast_count = (
            len(forecast_df) - len(eligible_forecasts)
        )

        if eligible_forecasts.empty:
            return {
                "period": period,
                "metrics": calculate_metrics(
                    pd.Series(dtype=float),
                    pd.Series(dtype=float),
                ),
                "records": [],
                "record_count": 0,
                "excluded_forecast_count": (
                    excluded_forecast_count
                ),
                "message": (
                    "No forecasts were published before "
                    "their delivery-day cutoff."
                ),
            }

        # Sort forecasts by publication time.
        eligible_forecasts = eligible_forecasts.sort_values(
            "publishTime"
        )

        # Select the latest eligible forecast for each
        # delivery period.
        selected_forecasts = (
            eligible_forecasts.drop_duplicates(
                subset=["startTime"],
                keep="last",
            )
        )

        selected_forecasts = selected_forecasts[
            [
                "startTime",
                "publishTime",
                "generation",
                "decisionCutoff",
            ]
        ].rename(
            columns={
                "generation": "forecastGeneration",
                "publishTime": "forecastPublishedAt",
            }
        )

        # Match forecast and actual generation.
        matched = pd.merge(
            actual_df,
            selected_forecasts,
            on="startTime",
            how="inner",
        )

        # Calculate forecast error.
        # Positive error = overforecasting.
        # Negative error = underforecasting.
        matched["error"] = (
            matched["forecastGeneration"]
            - matched["actualGeneration"]
        )

        # Calculate accuracy metrics.
        metrics = calculate_metrics(
            matched["actualGeneration"],
            matched["forecastGeneration"],
        )

        # Prepare API response records.
        records = []

        for row in matched.sort_values(
            "startTime"
        ).to_dict("records"):

            records.append({
                "startTime": row["startTime"].isoformat(),

                "forecastPublishedAt": (
                    row["forecastPublishedAt"].isoformat()
                ),

                "decisionCutoff": (
                    row["decisionCutoff"].isoformat()
                ),

                "actualGeneration": float(
                    row["actualGeneration"]
                ),

                "forecastGeneration": float(
                    row["forecastGeneration"]
                ),

                "error": float(row["error"]),
            })

        return {
            "period": period,
            "metrics": metrics,
            "records": records,
            "record_count": len(records),
            "excluded_forecast_count": (
                excluded_forecast_count
            ),
            "assumption": (
                "Purchasing decisions are analyzed for January "
                "2026. Each decision relates to delivery on the "
                "following day. The latest forecast published "
                "before 00:00 Europe/London on the delivery day "
                "is selected."
            ),
        }

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve data from Elexon.",
        )

    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected Elexon data: {exc}",
        )