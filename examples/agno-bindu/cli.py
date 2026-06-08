"""One-shot local runner.

    uv run python examples/agno-bindu/cli.py "paste contract text here..."

Reads OPENROUTER_API_KEY (and the optional BINDU_AGENT_* knobs) from
examples/agno-bindu/.env.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402

from agent import agent  # noqa: E402

console = Console()


def main() -> int:
    if len(sys.argv) < 2:
        console.print('[bold red]Error:[/bold red] pass the contract text, e.g. cli.py "..."')
        return 2
    result = agent.run(input=" ".join(sys.argv[1:]))
    console.print(Markdown(getattr(result, "content", None) or str(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
