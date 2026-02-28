import json
import logging
import os
from pathlib import Path

from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

from models import MessageModel
from prompts import SYSTEM_PROMPT
from tools import TOOL_LIST, execute_get_current_weather

# Load .env from project root (one level above agent-backend/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY", "")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

logger = logging.getLogger(__name__)


class AgentError(Exception):
    pass


def _make_chat_client() -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=PROJECT_ENDPOINT,
        api_key=AZURE_AI_API_KEY,
        api_version=AZURE_API_VERSION,
    )


def _build_messages(history: list[MessageModel], message: str) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        if msg.role == "system":
            logger.warning("Skipping system role message from history to prevent injection.")
            continue
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})
    return messages


async def run_agent(
    message: str,
    history: list[MessageModel],
    chat_client: AsyncAzureOpenAI,
    mcp_url: str = MCP_SERVER_URL,
) -> tuple[str, bool]:
    logger.info(
        "Agent invoked: message=%r, history_turns=%d",
        message[:80],
        len(history),
    )

    messages = _build_messages(history, message)
    tool_used = False

    # ── Round 1 ──────────────────────────────────────────────────────────────
    try:
        response = await chat_client.chat.completions.create(
            model=MODEL_DEPLOYMENT_NAME,
            messages=messages,
            tools=TOOL_LIST,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("LLM call failed (round 1): %s", exc)
        raise AgentError("model unavailable") from exc

    choice = response.choices[0]

    if choice.finish_reason == "tool_calls":
        tool_call = choice.message.tool_calls[0]

        # Parse tool arguments
        try:
            args = json.loads(tool_call.function.arguments)
            location = args["location"]
            if not isinstance(location, str) or not location:
                raise ValueError("location must be a non-empty string")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(
                "Malformed tool arguments: %r — %s",
                tool_call.function.arguments,
                exc,
            )
            return ("I encountered an issue. Could you rephrase it?", False)

        logger.info("Tool invocation: location=%r, mcp_url=%s", location, mcp_url)
        result = await execute_get_current_weather(location, mcp_url)
        logger.info("MCP response: location=%r, body=%s", location, result)

        # Append round 1 assistant message and tool result
        messages.append(choice.message)
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})

        # ── Round 2 ──────────────────────────────────────────────────────────
        try:
            response2 = await chat_client.chat.completions.create(
                model=MODEL_DEPLOYMENT_NAME,
                messages=messages,
                temperature=0.2,
            )
        except Exception as exc:
            logger.error("LLM call failed (round 2): %s", exc)
            raise AgentError("model unavailable") from exc

        reply_content = response2.choices[0].message.content
        tool_used = True
    else:
        # stop — direct answer or out-of-scope
        reply_content = choice.message.content

    if not reply_content:
        logger.error("LLM returned empty content")
        raise AgentError("LLM returned empty content")

    logger.info(
        "Agent reply: tool_used=%s, reply=%r",
        tool_used,
        reply_content[:120],
    )
    return (reply_content.strip(), tool_used)


async def run_agent_stream(
    message: str,
    history: list[MessageModel],
    chat_client: AsyncAzureOpenAI,
    mcp_url: str = MCP_SERVER_URL,
):
    """Async generator version of run_agent — yields SSE event dicts."""
    logger.info(
        "Agent stream invoked: message=%r, history_turns=%d",
        message[:80],
        len(history),
    )

    yield {"type": "status", "message": "Analyzing your question..."}

    messages = _build_messages(history, message)

    # ── Round 1 ──────────────────────────────────────────────────────────────
    try:
        response = await chat_client.chat.completions.create(
            model=MODEL_DEPLOYMENT_NAME,
            messages=messages,
            tools=TOOL_LIST,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("LLM call failed (round 1): %s", exc)
        yield {"type": "error", "message": "The weather service is currently unavailable. Please try again."}
        return

    choice = response.choices[0]

    if choice.finish_reason == "tool_calls":
        tool_call = choice.message.tool_calls[0]

        # Parse tool arguments
        try:
            args = json.loads(tool_call.function.arguments)
            location = args["location"]
            if not isinstance(location, str) or not location:
                raise ValueError("location must be a non-empty string")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(
                "Malformed tool arguments: %r — %s",
                tool_call.function.arguments,
                exc,
            )
            yield {"type": "error", "message": "I encountered an issue parsing the request. Could you rephrase it?"}
            return

        yield {"type": "status", "message": f"Fetching weather data for {location}..."}

        logger.info("Tool invocation: location=%r, mcp_url=%s", location, mcp_url)
        result = await execute_get_current_weather(location, mcp_url)
        logger.info("MCP response: location=%r, body=%s", location, result)

        # Append round 1 assistant message and tool result
        messages.append(choice.message)
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})

        yield {"type": "status", "message": "Generating response..."}

        # ── Round 2 ──────────────────────────────────────────────────────────
        try:
            response2 = await chat_client.chat.completions.create(
                model=MODEL_DEPLOYMENT_NAME,
                messages=messages,
                temperature=0.2,
            )
        except Exception as exc:
            logger.error("LLM call failed (round 2): %s", exc)
            yield {"type": "error", "message": "The weather service is currently unavailable. Please try again."}
            return

        reply_content = response2.choices[0].message.content
        if not reply_content:
            logger.error("LLM returned empty content (round 2)")
            yield {"type": "error", "message": "The model returned an empty response. Please try again."}
            return

        logger.info("Agent stream reply: tool_used=True, reply=%r", reply_content[:120])
        yield {"type": "result", "reply": reply_content.strip(), "tool_used": True}
    else:
        # stop — direct answer or out-of-scope
        reply_content = choice.message.content
        if not reply_content:
            logger.error("LLM returned empty content (round 1, no tool)")
            yield {"type": "error", "message": "The model returned an empty response. Please try again."}
            return

        logger.info("Agent stream reply: tool_used=False, reply=%r", reply_content[:120])
        yield {"type": "result", "reply": reply_content.strip(), "tool_used": False}
