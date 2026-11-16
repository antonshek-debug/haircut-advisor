"""haircut-advisor MCP server.

Lets Claude read the anonymous results of the haircut-advisor phone page.
Tools are added one at a time (Phase 7): suggest_haircuts, get_result,
class_stats.

Rules for this file (PLAN.md):
- Log to stderr only. Never print(): stdout carries the MCP messages.
- Keys come from server/.env (git-ignored) or the host's settings. Never log
  a key's value.
- Every tool is async, has a clear docstring, returns a string, logs with
  logging.info(), and turns database errors into a useful message.
- No tool lists individual results. One result can be read only by its code.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from supabase import AsyncClient, acreate_client

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

SHAPES = ("oval", "round", "square", "oblong", "heart", "diamond", "triangle")
LENGTHS = ("short", "medium", "long")
TEXTURES = ("straight", "wavy", "curly", "coily")
STYLES = ("masculine", "feminine", "neutral")

CAVEAT = "Face-shape haircut rules are stylist conventions, not science. Measurements are approximate."
DB_ERROR = (
    "The haircut database could not be reached. If the Supabase project is paused, "
    "open its dashboard to wake it, then try again."
)
MAX_CUTS = 5

mcp = FastMCP(
    "haircut-advisor",
    instructions=(
        "Reads anonymous results from the haircut-advisor phone page: face-shape "
        "measurements, the closest shapes, and haircut suggestions. "
        "Face-shape haircut rules are stylist conventions, not science; pass that caveat on."
    ),
)

_client: AsyncClient | None = None


async def db() -> AsyncClient:
    """One Supabase connection, made on first use with the secret key."""
    global _client
    if _client is None:
        url, key = (os.getenv(name) for name in REQUIRED_SETTINGS)
        if not url or not key:
            raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_KEY is missing")
        _client = await acreate_client(url, key)
    return _client


def clean(value: str | None) -> str | None:
    """Lower case, no spaces around. Empty and "any" mean "no filter"."""
    if value is None:
        return None
    value = value.strip().lower()
    return None if value in ("", "any") else value


def invalid(value: str | None, allowed: tuple[str, ...], label: str) -> str | None:
    """A message if the value is not allowed, else None."""
    if value is None or value in allowed:
        return None
    return f'"{value}" is not a valid {label}. Valid values: {", ".join(allowed)}.'


async def haircut_text(shape: str, length: str | None, texture: str | None, style: str | None) -> str:
    """Suggestions for one valid shape and optional filters, as text."""
    client = await db()
    response = (
        await client.table("haircuts")
        .select("name, length, textures, styles, reason, avoid")
        .eq("face_shape", shape)
        .order("id")
        .execute()
    )
    rows = response.data or []
    matches = [
        row
        for row in rows
        if (length is None or row["length"] == length)
        and (texture is None or texture in row["textures"])
        and (style is None or style in row["styles"])
    ]

    filters = ", ".join(
        f"{label}: {value}"
        for label, value in (("length", length), ("texture", texture), ("style", style))
        if value
    )
    article = "an" if shape[0] == "o" else "a"
    lines = [f"Haircuts for {article} {shape} face" + (f" ({filters})" if filters else "") + ":"]

    if not matches:
        lines.append("No cut in the table matches all of these filters. Try again with fewer filters.")
    else:
        for number, row in enumerate(matches[:MAX_CUTS], start=1):
            lines.append(f"{number}. {row['name']} ({row['length']}): {row['reason']}")
        if len(matches) < 3:
            lines.append(
                f"Only {len(matches)} cut{'s' if len(matches) != 1 else ''} in the table "
                "match all of these filters."
            )

    avoid_from = matches or rows
    if avoid_from:
        lines.append(f"Avoid: {avoid_from[0]['avoid']}")
    lines.append(f"Note: {CAVEAT}")
    return "\n".join(lines)


@mcp.tool
async def suggest_haircuts(
    face_shape: str,
    length: str | None = None,
    texture: str | None = None,
    style: str | None = None,
) -> str:
    """Suggest haircuts for a face shape.

    Use this when someone names a face shape and wants haircut ideas.

    Args:
        face_shape: One of oval, round, square, oblong, heart, diamond, triangle.
        length: Optional. short, medium or long. Only cuts of that length are returned.
        texture: Optional. The person's hair texture: straight, wavy, curly or coily.
        style: Optional. masculine, feminine or neutral. The person chooses this;
            never guess it from a name or a description.

    Returns:
        Up to 5 cuts with a reason each, one thing to avoid, and a caveat.
        If the shape or a filter is not valid, returns the list of valid values.
    """
    log.info("suggest_haircuts(face_shape=%r, length=%r, texture=%r, style=%r)", face_shape, length, texture, style)

    shape = clean(face_shape)
    length, texture, style = clean(length), clean(texture), clean(style)

    if shape not in SHAPES:
        return f'"{face_shape}" is not a valid face shape. Valid shapes: {", ".join(SHAPES)}.'
    problem = (
        invalid(length, LENGTHS, "length")
        or invalid(texture, TEXTURES, "texture")
        or invalid(style, STYLES, "style")
    )
    if problem:
        return problem

    try:
        return await haircut_text(shape, length, texture, style)
    except Exception:
        log.exception("suggest_haircuts failed")
        return DB_ERROR


def main() -> None:
    for name in REQUIRED_SETTINGS:
        log.info("%s is %s", name, "set" if os.getenv(name) else "MISSING")
    log.info("Starting haircut-advisor on stdio")
    mcp.run()  # stdio is the default transport


if __name__ == "__main__":
    main()
