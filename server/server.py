"""haircut-advisor MCP server.

Phase 6 scaffold: the server starts and connects over stdio. It has no tools
yet; they are added one at a time in Phase 7.

Rules for this file (PLAN.md):
- Log to stderr only. Never print(): stdout carries the MCP messages.
- Keys come from server/.env (git-ignored) or the host's settings. Never log
  a key's value.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("haircut-advisor")

# server/.env sits next to this file, so it loads whatever folder the client
# starts the server from.
load_dotenv(Path(__file__).with_name(".env"))

REQUIRED_SETTINGS = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")

mcp = FastMCP(
    "haircut-advisor",
    instructions=(
        "Reads anonymous results from the haircut-advisor phone page: face-shape "
        "measurements, the closest shapes, and haircut suggestions. "
        "No tools are available yet."
    ),
)


def main() -> None:
    for name in REQUIRED_SETTINGS:
        log.info("%s is %s", name, "set" if os.getenv(name) else "MISSING")
    log.info("Starting haircut-advisor on stdio")
    mcp.run()  # stdio is the default transport


if __name__ == "__main__":
    main()
