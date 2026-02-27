import os
import logging
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Load .env from project root (one level above mcp-server/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

WEATHERSTACK_BASE_URL = "http://api.weatherstack.com/current"
WEATHERSTACK_API_KEY = os.getenv("WEATHERSTACK_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not WEATHERSTACK_API_KEY:
        logger.warning(
            "WEATHERSTACK_API_KEY is not set. "
            "The /weather endpoint will return 503 until the key is configured."
        )
    yield


app = FastAPI(
    title="MCP Weather Server",
    description="Secure REST wrapper around the Weatherstack API.",
    version="1.0.0",
    lifespan=lifespan,
)


class UnitsEnum(str, Enum):
    fahrenheit = "f"
    metric = "m"
    scientific = "s"


class LocationModel(BaseModel):
    name: str
    country: str
    region: str
    lat: float
    lon: float


class CurrentWeatherModel(BaseModel):
    temperature: int
    feels_like: int
    humidity: int
    wind_speed: int
    wind_direction: str
    description: str
    uv_index: int
    visibility: int
    cloud_cover: int


class WeatherSuccessResponse(BaseModel):
    success: bool = True
    location: LocationModel
    current: CurrentWeatherModel
    units: str


class WeatherErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: int


class HealthResponse(BaseModel):
    status: str
    api_key_configured: bool


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        api_key_configured=bool(WEATHERSTACK_API_KEY),
    )


@app.get("/weather", response_model=WeatherSuccessResponse)
async def get_weather(
    location: str = Query(..., min_length=1),
    units: UnitsEnum = Query(UnitsEnum.fahrenheit),
) -> WeatherSuccessResponse:
    if not WEATHERSTACK_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Weather service is unavailable: API key not configured.",
        )

    params = {
        "access_key": WEATHERSTACK_API_KEY,
        "query": location,
        "units": units.value,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                WEATHERSTACK_BASE_URL, params=params, timeout=10.0
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to weather service timed out.",
        )
    except httpx.HTTPStatusError as exc:
        try:
            body = exc.response.json()
        except Exception:
            body = exc.response.text
        logger.error("Weatherstack HTTP error %s: %s", exc.response.status_code, body)
        raise HTTPException(
            status_code=502,
            detail={
                "upstream_status": exc.response.status_code,
                "upstream_body": body,
            },
        )

    data = response.json()

    # Weatherstack always returns HTTP 200; errors are signaled in the body
    if data.get("success") is False:
        error_info = data.get("error", {})
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": error_info.get("info", "Unknown error from weather service."),
                "code": error_info.get("code", 0),
            },
        )

    loc = data.get("location", {})
    current = data.get("current", {})

    descriptions = current.get("weather_descriptions", [])
    description = descriptions[0] if descriptions else ""

    location_model = LocationModel(
        name=loc.get("name", ""),
        country=loc.get("country", ""),
        region=loc.get("region", ""),
        lat=float(loc.get("lat", 0)),
        lon=float(loc.get("lon", 0)),
    )

    current_model = CurrentWeatherModel(
        temperature=current.get("temperature", 0),
        feels_like=current.get("feelslike", 0),
        humidity=current.get("humidity", 0),
        wind_speed=current.get("wind_speed", 0),
        wind_direction=current.get("wind_dir", ""),
        description=description,
        uv_index=current.get("uv_index", 0),
        visibility=current.get("visibility", 0),
        cloud_cover=current.get("cloudcover", 0),
    )

    return WeatherSuccessResponse(
        location=location_model,
        current=current_model,
        units=units.value,
    )


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("MCP_PORT", "8000")),
        reload=False,
    )
