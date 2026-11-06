from datetime import date, datetime, time, timedelta, timezone

import httpx


BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"


def to_utc_string(value: datetime) -> str:
    """Convert a datetime to an ISO-8601 UTC string."""

    return value.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


async def fetch_dataset(
    dataset: str,
    start: datetime,
    end: datetime
) -> list[dict]:
    """
    Fetch records from an Elexon dataset.

    The query uses a publication-time window. The returned records
    must still be checked for their target period and relevant fields.
    """

    url = f"{BASE_URL}/{dataset}/stream"

    params = {
        "publishDateTimeFrom": to_utc_string(start),
        "publishDateTimeTo": to_utc_string(end)
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    # Handle common JSON response structures.
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "results", "result"):
            if isinstance(payload.get(key), list):
                return payload[key]

    raise ValueError(
        f"Unexpected response structure from Elexon dataset {dataset}"
    )


async def fetch_wind_actuals() -> list[dict]:
    """Fetch actual generation records published during January 2026."""

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)

    records = await fetch_dataset("FUELHH", start, end)

    return [
        record
        for record in records
        if str(record.get("fuelType", "")).upper() == "WIND"
    ]


async def fetch_wind_forecasts() -> list[dict]:
    """
    Fetch forecasts published around the January 2026 analysis period.

    December records are included because a forecast for early January
    may have been published in December.
    """

    start = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)

    return await fetch_dataset("WINDFOR", start, end)