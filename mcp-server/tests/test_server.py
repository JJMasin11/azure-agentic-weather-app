import sys
import os

# Ensure the mcp-server directory is on the path so `mcp_server` can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import respx
import httpx
import pytest
from fastapi.testclient import TestClient

import mcp_server as server

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

# Error code 615 = invalid / unrecognised location → server must return 404
MOCK_WEATHERSTACK_LOCATION_ERROR = {
    "success": False,
    "error": {
        "code": 615,
        "type": "request_failed",
        "info": "Please specify a valid location identifier.",
    },
}

# Error code 104 = usage limit reached → server must return 400
MOCK_WEATHERSTACK_GENERIC_ERROR = {
    "success": False,
    "error": {
        "code": 104,
        "type": "usage_limit_reached",
        "info": "Your monthly API request volume has been reached.",
    },
}


def test_missing_location_returns_400():
    response = client.get("/weather")
    assert response.status_code == 400
    assert "error" in response.json()


def test_invalid_units_returns_400():
    response = client.get("/weather", params={"location": "Austin", "units": "kelvin"})
    assert response.status_code == 400
    assert "error" in response.json()


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

    # Flat top-level structure required by spec
    assert data["location"] == "Austin"
    assert data["temperature"] == 72
    assert data["feels_like"] == 70           # feelslike → feels_like
    assert data["wind_direction"] == "S"      # wind_dir → wind_direction
    assert data["cloud_cover"] == 5           # cloudcover → cloud_cover
    assert data["weather_description"] == "Sunny"
    assert data["humidity"] == 45
    assert data["uv_index"] == 6
    assert data["visibility"] == 10

    # Old nested keys must not be present
    assert "success" not in data
    assert "current" not in data
    assert "units" not in data


@respx.mock
def test_location_not_found_returns_404():
    respx.get(server.WEATHERSTACK_BASE_URL).mock(
        return_value=httpx.Response(200, json=MOCK_WEATHERSTACK_LOCATION_ERROR)
    )

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        response = client.get("/weather", params={"location": "BadLocation"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert response.status_code == 404
    assert response.json() == {"error": "Location not found."}


@respx.mock
def test_generic_api_error_returns_400():
    respx.get(server.WEATHERSTACK_BASE_URL).mock(
        return_value=httpx.Response(200, json=MOCK_WEATHERSTACK_GENERIC_ERROR)
    )

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        response = client.get("/weather", params={"location": "Austin"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert response.status_code == 400
    assert "error" in response.json()


def test_missing_api_key_returns_503(monkeypatch):
    monkeypatch.setattr(server, "WEATHERSTACK_API_KEY", None)
    response = client.get("/weather", params={"location": "Austin"})
    assert response.status_code == 503
    assert "error" in response.json()


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


@respx.mock
def test_timeout_returns_502():
    respx.get(server.WEATHERSTACK_BASE_URL).mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    original_key = server.WEATHERSTACK_API_KEY
    server.WEATHERSTACK_API_KEY = "test_key"
    try:
        response = client.get("/weather", params={"location": "Austin"})
    finally:
        server.WEATHERSTACK_API_KEY = original_key

    assert response.status_code == 502
    assert "error" in response.json()
