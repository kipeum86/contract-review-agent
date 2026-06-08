"""Contract Review Agent — an agno agent that loads the upstream project's own
Claude Code skills and reviews contracts over A2A.

No server is started here. `bindu_agent.py` imports `agent` and exposes it over A2A;
`cli.py` imports it for one-shot local runs.
"""

from __future__ import annotations

import os

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from prompts import AGENT_DESCRIPTION, AGENT_NAME, SYSTEM_PROMPT
from skills_loader import build_skills, load_policy


def _build_model() -> OpenRouter:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to your .env (see .env.example)."
        )
    return OpenRouter(
        id=os.getenv("BINDU_AGENT_MODEL", "anthropic/claude-sonnet-4.5"),
        api_key=api_key,
        max_tokens=int(os.getenv("BINDU_AGENT_MAX_TOKENS", "8192")),
    )


def build_agent() -> Agent:
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=SYSTEM_PROMPT,
        model=_build_model(),
        # Loads the upstream .claude/skills/ in place and hands the agent the
        # get_skill_instructions / get_skill_reference / get_skill_script tools.
        skills=build_skills(),
        # Read-only access to the upstream policy YAMLs (review modes, families).
        tools=[load_policy],
        markdown=True,
    )


agent: Agent = build_agent()
