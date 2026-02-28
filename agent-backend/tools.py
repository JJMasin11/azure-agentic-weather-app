import json
import logging

import httpx

logger = logging.getLogger(__name__)

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Retrieves current weather for a location. Call for any weather-related query.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City or location name"},
            },
            "required": ["location"],
        },
    },
}

TOOL_LIST = [WEATHER_TOOL]


async def execute_get_current_weather(location: str, mcp_url: str) -> str:
    """Call the MCP server. Always returns a JSON string, never raises."""
    url = f"{mcp_url}/weather"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"location": location}, timeout=10.0)

        if response.status_code == 200:
            return response.text

        if response.status_code == 404:
            logger.error("MCP 404: location=%r not found", location)
            return json.dumps({"error": f"Location '{location}' was not found."})

        body = response.json()
        error_msg = body.get("error", "Unknown error from weather service.")
        logger.error(
            "MCP error %d: location=%r, message=%s",
            response.status_code,
            location,
            error_msg,
        )
        return json.dumps({"error": error_msg})

    except httpx.TimeoutException:
        logger.error("MCP timeout for location=%r", location)
        return json.dumps({"error": "Weather service timed out."})
    except httpx.RequestError:
        logger.error("MCP unreachable for location=%r", location)
        return json.dumps({"error": "Weather service is unreachable."})
