import os
import logging
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load .env from project root (one level above mcp-server/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

WEATHERSTACK_BASE_URL = "http://api.weatherstack.com/current"
WEATHERSTACK_API_KEY = os.getenv("WEATHERSTACK_API_KEY")

# Weatherstack error codes that indicate an invalid or unrecognised location
_LOCATION_NOT_FOUND_CODES = {601, 615}

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


# ── Custom exception handlers ────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 400 (not FastAPI's default 422) for missing / invalid parameters."""
    return JSONResponse(status_code=400, content={"error": "Invalid request parameters."})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Normalise all HTTP errors to {"error": "..."} instead of {"detail": ...}."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    elif isinstance(exc.detail, str):
        content = {"error": exc.detail}
    else:
        content = {"error": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


# ── Pydantic models ──────────────────────────────────────────────────────────

class UnitsEnum(str, Enum):
    fahrenheit = "f"
    metric = "m"
    scientific = "s"


class WeatherResponse(BaseModel):
    """Flat normalised weather response matching the spec schema."""
    location: str
    temperature: int
    feels_like: int
    humidity: int
    wind_speed: int
    wind_direction: str
    weather_description: str
    uv_index: int
    visibility: int
    cloud_cover: int


class HealthResponse(BaseModel):
    status: str
    api_key_configured: bool


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        api_key_configured=bool(WEATHERSTACK_API_KEY),
    )


@app.get("/weather", response_model=WeatherResponse)
async def get_weather(
    location: str = Query(..., min_length=1),
    units: UnitsEnum = Query(UnitsEnum.fahrenheit),
) -> WeatherResponse:
    logger.info("Incoming request: location=%r units=%s", location, units.value)

    if not WEATHERSTACK_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={"error": "Weather service is unavailable: API key not configured."},
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
        logger.error("Request to Weatherstack timed out for location: %r", location)
        raise HTTPException(
            status_code=502,
            detail={"error": "Weather service timed out."},
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Weatherstack HTTP error %s for location %r",
            exc.response.status_code,
            location,
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "External weather service returned an error."},
        )

    data = response.json()

    # Weatherstack always returns HTTP 200; errors are signalled in the body
    if data.get("success") is False:
        error_info = data.get("error", {})
        code = error_info.get("code", 0)
        message = error_info.get("info", "Unknown error from weather service.")

        if code in _LOCATION_NOT_FOUND_CODES:
            logger.warning(
                "Location not found: %r (Weatherstack code %s)", location, code
            )
            raise HTTPException(
                status_code=404,
                detail={"error": "Location not found."},
            )

        logger.error(
            "Weatherstack error code %s for location %r: %s", code, location, message
        )
        raise HTTPException(
            status_code=400,
            detail={"error": message},
        )

    loc = data.get("location", {})
    current = data.get("current", {})

    descriptions = current.get("weather_descriptions", [])
    description = descriptions[0] if descriptions else ""

    return WeatherResponse(
        location=loc.get("name", ""),
        temperature=current.get("temperature", 0),
        feels_like=current.get("feelslike", 0),
        humidity=current.get("humidity", 0),
        wind_speed=current.get("wind_speed", 0),
        wind_direction=current.get("wind_dir", ""),
        weather_description=description,
        uv_index=current.get("uv_index", 0),
        visibility=current.get("visibility", 0),
        cloud_cover=current.get("cloudcover", 0),
    )


if __name__ == "__main__":
    uvicorn.run(
        "mcp_server:app",
        host="0.0.0.0",
        port=int(os.getenv("MCP_PORT", "8000")),
        reload=False,
    )
