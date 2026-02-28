from typing import Literal

from pydantic import BaseModel, Field


class MessageModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[MessageModel] = []


class ChatResponse(BaseModel):
    reply: str
    tool_used: bool


class AgentHealthResponse(BaseModel):
    status: str
    model: str
    mcp_url: str
