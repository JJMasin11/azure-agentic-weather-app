"""
frontend/app.py — Streamlit chat UI for the Azure Agentic Weather App.

Connects to the agent backend via POST /chat/stream (SSE) and renders
real-time loading stages and markdown replies.
"""

import json
import os

import httpx
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
AGENT_STREAM_URL = f"http://localhost:{AGENT_PORT}/chat/stream"

st.set_page_config(page_title="Weather Agent", page_icon="⛅", layout="centered")
st.title("⛅ Weather Agent")

# ── Session state ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content, tool_used}

# ── Render chat history ────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tool_used"):
            st.caption("☁ Weather data fetched")

# ── Chat input ─────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about the weather..."):
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt, "tool_used": False})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build history payload from all prior messages (excluding the current one)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]  # exclude current user message
    ]

    payload = {"message": prompt, "history": history}

    # ── Stream response ────────────────────────────────────────────────────────
    with st.chat_message("assistant"):
        reply_text = None
        tool_used = False
        error_message = None

        try:
            with st.status("Thinking...", expanded=True) as status_box:
                with httpx.Client(timeout=60.0) as client:
                    with client.stream("POST", AGENT_STREAM_URL, json=payload) as response:
                        if response.status_code != 200:
                            error_message = f"Agent returned error {response.status_code}."
                            status_box.update(label="Error", state="error", expanded=False)
                        else:
                            for line in response.iter_lines():
                                if not line.startswith("data: "):
                                    continue
                                raw = line[len("data: "):]
                                try:
                                    event = json.loads(raw)
                                except json.JSONDecodeError:
                                    continue

                                etype = event.get("type")
                                if etype == "status":
                                    st.write(event.get("message", ""))
                                elif etype == "result":
                                    reply_text = event.get("reply", "")
                                    tool_used = event.get("tool_used", False)
                                    status_box.update(label="Done", state="complete", expanded=False)
                                elif etype == "error":
                                    error_message = event.get("message", "An error occurred.")
                                    status_box.update(label="Error", state="error", expanded=False)

        except httpx.ConnectError:
            error_message = "Could not connect to the weather agent. Is it running?"
        except Exception as exc:
            error_message = str(exc)

        if error_message:
            st.error(error_message)
            # Don't add assistant message on error
        elif reply_text is not None:
            st.markdown(reply_text)
            if tool_used:
                st.caption("☁ Weather data fetched")
            # Persist to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply_text,
                "tool_used": tool_used,
            })
