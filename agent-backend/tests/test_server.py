import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure agent-backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent_server as server
from agent import AgentError

client = TestClient(server.app)


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "mcp_url" in data


# ── /chat — success ───────────────────────────────────────────────────────────

def test_chat_success_with_tool():
    with patch.object(server, "_chat_client", MagicMock()), \
         patch("agent_server.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = ("It's sunny in Austin at 72°F.", True)
        response = client.post(
            "/chat",
            json={"message": "What is the weather in Austin?", "history": []},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "It's sunny in Austin at 72°F."
    assert data["tool_used"] is True


def test_chat_success_no_tool():
    with patch.object(server, "_chat_client", MagicMock()), \
         patch("agent_server.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (
            "I'm specialized in weather information. I can tell you about current "
            "conditions for any location — just ask!",
            False,
        )
        response = client.post(
            "/chat",
            json={"message": "Tell me a joke.", "history": []},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tool_used"] is False
    assert data["reply"]


# ── /chat — validation errors ─────────────────────────────────────────────────

def test_chat_missing_message_returns_400():
    response = client.post("/chat", json={"history": []})
    assert response.status_code == 400
    assert "error" in response.json()


def test_chat_empty_message_returns_400():
    response = client.post("/chat", json={"message": "", "history": []})
    assert response.status_code == 400
    assert "error" in response.json()


# ── /chat — error paths ───────────────────────────────────────────────────────

def test_chat_agent_error_returns_500():
    with patch.object(server, "_chat_client", MagicMock()), \
         patch("agent_server.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = AgentError("model unavailable")
        response = client.post(
            "/chat",
            json={"message": "What is the weather in Austin?", "history": []},
        )

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "model unavailable" in data["error"]


def test_chat_unexpected_exception_returns_500():
    with patch.object(server, "_chat_client", MagicMock()), \
         patch("agent_server.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("something broke")
        response = client.post(
            "/chat",
            json={"message": "What is the weather in Austin?", "history": []},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "An unexpected error occurred."}
