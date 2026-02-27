import sys
import os

# Ensure the mcp-server directory is on the path so `server` can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import respx
import httpx
import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)

MOCK_WEATHERSTACK_SUCCESS = {
    "request": {"type": "City", "query": "Austin, Texas", "language": "en", "unit": "f"},
    "location": {
        "name": "Austin",
        "country": "United States of America",
        "region": "Texas",
        "lat": "30.283",
        "lon": "-97.742",
        "timezone_id": "America/Chicago",
        "localtime": "2026-02-27 12:00",
        "localtime_epoch": 1740657600,
        "utc_offset": "-6.0",
    },
    "current": {
        "observation_time": "06:00 PM",
        "temperature": 72,
        "weather_code": 113,
        "weather_icons": ["https://cdn.worldweatheronline.com/images/wsymbols01_png_64/wsymbol_0001_sunny.png"],
        "weather_descriptions": ["Sunny"],
        "wind_speed": 10,
        "wind_degree": 180,
        "wind_dir": "S",
        "pressure": 1015,
        "precip": 0.0,
        "humidity": 45,
        "cloudcover": 5,
        "feelslike": 70,
        "uv_index": 6,
        "visibility": 10,
        "is_day": "yes",
    },
}

MOCK_WEATHERSTACK_ERROR = {
    "success": False,
    "error": {
        "code": 615,
        "type": "request_failed",
        "info": "Your API request failed. Please try again or contact support.",
    },
}


def test_missing_location_returns_422():
    response = client.get("/weather")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("location" in str(err).lower() for err in detail)


def test_invalid_units_returns_422():
    response = client.get("/weather", params={"location": "Austin", "units": "kelvin"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("units" in str(err).lower() for err in detail)


@respx.mock
def test_successful_response_normalized_shape():
    respx.get(server.WEATHERSTACK_BASE_URL).mock(
        return_value=httpx.Response(200, json=MOCK_WEATHERSTACK_SUCCESS)
    )

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        response = client.get("/weather", params={"location": "Austin, Texas"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["units"] == "f"

    loc = data["location"]
    assert loc["name"] == "Austin"
    assert loc["country"] == "United States of America"
    assert loc["lat"] == 30.283
    assert loc["lon"] == -97.742

    current = data["current"]
    assert current["temperature"] == 72
    assert current["feels_like"] == 70        # feelslike → feels_like
    assert current["wind_direction"] == "S"   # wind_dir → wind_direction
    assert current["cloud_cover"] == 5        # cloudcover → cloud_cover
    assert current["description"] == "Sunny"
    assert current["humidity"] == 45
    assert current["uv_index"] == 6
    assert current["visibility"] == 10


@respx.mock
def test_weatherstack_api_error_normalized():
    respx.get(server.WEATHERSTACK_BASE_URL).mock(
        return_value=httpx.Response(200, json=MOCK_WEATHERSTACK_ERROR)
    )

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        response = client.get("/weather", params={"location": "BadLocation"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == 615
    assert detail["success"] is False


def test_missing_api_key_returns_503(monkeypatch):
    monkeypatch.setattr(server, "WEATHERSTACK_API_KEY", None)
    response = client.get("/weather", params={"location": "Austin"})
    assert response.status_code == 503


def test_health_endpoint_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["api_key_configured"], bool)


@respx.mock
def test_default_units_is_fahrenheit():
    captured_request = None

    def capture(request):
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=MOCK_WEATHERSTACK_SUCCESS)

    respx.get(server.WEATHERSTACK_BASE_URL).mock(side_effect=capture)

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        client.get("/weather", params={"location": "Austin"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert captured_request is not None
    query_params = dict(httpx.URL(str(captured_request.url)).params)
    assert query_params.get("units") == "f"
