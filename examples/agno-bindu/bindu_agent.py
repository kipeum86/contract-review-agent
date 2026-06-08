"""Contract Review Agent exposed as a Bindu A2A agent.

Synchronous — agno's Skills tools are plain functions, so there is no MCP server and
no background event loop here (unlike the MCP examples). The Bindu handler calls
`agent.run(...)` directly.

Run:  uv run python examples/agno-bindu/bindu_agent.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

from agent import agent  # noqa: E402
from prompts import AGENT_DESCRIPTION  # noqa: E402

from bindu.penguin.bindufy import bindufy  # noqa: E402


async def handler(messages):
    """Async Bindu handler.

    We `await agent.arun(...)` rather than calling the sync `agent.run(...)` so the
    server's event loop stays responsive while a (possibly minute-long) review runs —
    a blocking sync call here would stall /health and every other request until it
    finished. Bindu normalizes the inbound A2A message to OpenAI-style
    [{"role": "user"|"assistant", "content": "..."}] before calling us, with text
    parts joined by spaces.
    """
    user_content = " ".join(
        (m.get("content") or "") for m in (messages or []) if m.get("role") == "user"
    ).strip()
    if not user_content:
        return (
            "Paste a contract (or a single clause) as text and I'll review it "
            "clause-by-clause — risk grades, redline suggestions, and negotiation "
            "points. Tell me which side you're on, your leverage, and the review mode "
            "(strict / moderate / loose) for a sharper read."
        )
    result = await agent.arun(user_content)
    return getattr(result, "content", None) or str(result)


config = {
    # Ends up inside the public agent-card DID once `expose` is on, so the default is
    # a clearly-fake placeholder rather than something that looks like a real address.
    "author": os.getenv("BINDU_AGENT_AUTHOR", "your_email_here@example.com"),
    "name": os.getenv("BINDU_AGENT_NAME", "bindu-contract-review"),
    "description": AGENT_DESCRIPTION,
    "deployment": {
        "url": os.getenv("BINDU_AGENT_URL", "http://localhost:3773"),
        # Opt-in only. Setting BINDU_EXPOSE=true asks Bindu to open an FRP reverse
        # tunnel that makes this agent's HTTP endpoint reachable on the public
        # internet. The endpoint is unauthenticated and any model-API key configured
        # here is on the billing path. Leave this off unless you have read the
        # README's "Network exposure & dependencies" section.
        "expose": os.getenv("BINDU_EXPOSE", "false").lower() == "true",
        "cors_origins": ["http://localhost:5173"],
    },
    "capabilities": {"streaming": False},
}


if __name__ == "__main__":
    bindufy(config, handler)
