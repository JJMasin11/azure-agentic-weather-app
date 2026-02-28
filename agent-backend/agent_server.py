import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent import (
    AgentError,
    MCP_SERVER_URL,
    MODEL_DEPLOYMENT_NAME,
    _make_chat_client,
    run_agent,
)
from openai import AsyncAzureOpenAI
from models import AgentHealthResponse, ChatRequest, ChatResponse

# Load .env from project root (one level above agent-backend/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_chat_client: AsyncAzureOpenAI | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _chat_client
    try:
        _chat_client = _make_chat_client()
        logger.info("Chat client initialized successfully.")
    except Exception as exc:
        logger.warning("Failed to initialize chat client: %s", exc)
    yield
    if _chat_client is not None:
        await _chat_client.close()
        logger.info("Chat client closed.")


app = FastAPI(
    title="Agent Backend",
    description="LLM agent backend for the Azure Agentic Weather App.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Custom exception handlers ────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"error": "Invalid request body."})


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=AgentHealthResponse)
async def health() -> AgentHealthResponse:
    return AgentHealthResponse(
        status="ok",
        model=MODEL_DEPLOYMENT_NAME,
        mcp_url=MCP_SERVER_URL,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    logger.info(
        "Incoming POST /chat: message=%r, history_count=%d",
        request.message[:80],
        len(request.history),
    )

    if _chat_client is None:
        logger.error("AgentError in /chat: chat client not initialized")
        return JSONResponse(
            status_code=500,
            content={"error": "Chat service not available."},
        )

    try:
        reply, tool_used = await run_agent(
            message=request.message,
            history=request.history,
            chat_client=_chat_client,
            mcp_url=MCP_SERVER_URL,
        )
        return ChatResponse(reply=reply, tool_used=tool_used)
    except AgentError as exc:
        logger.error("AgentError in /chat: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception:
        logger.error("Unexpected exception in /chat", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "An unexpected error occurred."},
        )


if __name__ == "__main__":
    uvicorn.run(
        "agent_server:app",
        host="0.0.0.0",
        port=int(os.getenv("AGENT_PORT", "8001")),
        reload=False,
    )
