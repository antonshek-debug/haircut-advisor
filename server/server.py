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
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
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
    """Suggest haircuts for a face shape. Read-only: it changes nothing.

    Use this when someone names a face shape and wants haircut ideas.

    Returns up to 5 cuts with a reason each, one thing to avoid, and a
    caveat. If no cut matches all the filters, says so and suggests fewer
    filters; if fewer than 3 match, says how many. If the shape or a filter
    is not valid, returns the list of valid values.

    Args:
        face_shape: One of oval, round, square, oblong, heart, diamond, triangle.
        length: Optional. short, medium or long. Only cuts of that length are returned.
        texture: Optional. The person's hair texture: straight, wavy, curly or coily.
        style: Optional. masculine, feminine or neutral. The person chooses this;
            never guess it from a name or a description.
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


CODE_PATTERN = re.compile(r"^[A-HJ-NP-Z2-9]{6}$")  # same rule as db/schema.sql
NO_RESULT = "No result with that code."
RESULT_COLUMNS = (
    "code, created_at, length_ratio, forehead_ratio, jaw_ratio, jaw_angle, "
    "shape_1, score_1, shape_2, score_2, length_pref, texture, style"
)


@mcp.tool
async def get_result(code: str) -> str:
    """Read one saved result by its 6-character code. Read-only: it changes nothing.

    Use this when someone gives the code the phone page showed them.
    Case and spaces in the code do not matter.

    Returns the two closest face shapes with scores, the 4 measurements, the
    person's own choices (length, texture, style), and haircut suggestions
    for the closest shape and those choices. If no result has that code, or
    the code is not 6 valid characters, returns "No result with that code."
    There is no way to list results or search them.

    Args:
        code: The 6-character code from the phone page, for example "K7MP3Q".
    """
    log.info("get_result(code=%r)", code)

    wanted = "".join((code or "").split()).upper()
    if not CODE_PATTERN.match(wanted):
        return NO_RESULT

    try:
        client = await db()
        response = (
            await client.table("results").select(RESULT_COLUMNS).eq("code", wanted).limit(1).execute()
        )
        if not response.data:
            return NO_RESULT
        row = response.data[0]
        length = None if row["length_pref"] == "any" else row["length_pref"]
        suggestions = await haircut_text(row["shape_1"], length, row["texture"], row["style"])
    except Exception:
        log.exception("get_result failed")
        return DB_ERROR

    lines = [
        f"Result {row['code']} (saved {row['created_at'][:10]})",
        f"Closest shape: {row['shape_1']} (score {row['score_1']:.2f})",
        f"Second closest: {row['shape_2']} (score {row['score_2']:.2f})",
        "Measurements:",
        f"- Face length / cheekbone width: {row['length_ratio']:.3f}",
        f"- Forehead width / cheekbone width: {row['forehead_ratio']:.3f}",
        f"- Jaw width / cheekbone width: {row['jaw_ratio']:.3f}",
        f"- Jaw angle: {row['jaw_angle']:.1f} degrees",
        f"Their choices: length {row['length_pref']}, texture {row['texture']}, style {row['style']}",
        "",
        suggestions,
    ]
    return "\n".join(lines)


@mcp.tool
async def class_stats() -> str:
    """Totals for all saved results: how many people got each closest face shape.
    Read-only: it changes nothing.

    Use this for questions about the whole class, such as "which face shape is
    most common?". It returns totals only, never single results or codes.

    Returns the number of results, the date range, and for each of the 7
    shapes the count and percent of results where it was the closest shape.
    If nothing is saved yet, returns "No results have been saved yet."
    """
    log.info("class_stats()")

    try:
        client = await db()
        response = await client.table("results").select("shape_1, created_at").execute()
    except Exception:
        log.exception("class_stats failed")
        return DB_ERROR

    rows = response.data or []
    if not rows:
        return "No results have been saved yet."

    total = len(rows)
    days = sorted(row["created_at"][:10] for row in rows)
    counts = {shape: 0 for shape in SHAPES}
    for row in rows:
        counts[row["shape_1"]] += 1

    lines = [
        f"{total} result{'s' if total != 1 else ''} saved, from {days[0]} to {days[-1]}.",
        "Closest face shape:",
    ]
    for shape in sorted(SHAPES, key=lambda s: (-counts[s], SHAPES.index(s))):
        lines.append(f"- {shape}: {counts[shape]} ({100 * counts[shape] / total:.0f}%)")
    lines.append(f"Note: {CAVEAT}")
    return "\n".join(lines)


@mcp.custom_route("/", methods=["GET"])
async def home(request: Request) -> PlainTextResponse:
    """Plain page for the HTTP server. Open it once to wake Render before a demo."""
    return PlainTextResponse("haircut-advisor MCP server is running. The MCP address is /mcp.")


def main() -> None:
    for name in REQUIRED_SETTINGS:
        log.info("%s is %s", name, "set" if os.getenv(name) else "MISSING")
    # MCP_TRANSPORT picks the transport (PLAN.md Phase 8):
    #   unset or "stdio" -> local clients (Claude Desktop, Claude Code)
    #   "http"           -> Render; listens on 0.0.0.0:$PORT at /mcp
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "http":
        port = int(os.getenv("PORT", "8000"))
        log.info("Starting haircut-advisor on HTTP, port %d, path /mcp", port)
        mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
    else:
        log.info("Starting haircut-advisor on stdio")
        mcp.run()  # stdio is the default transport


if __name__ == "__main__":
    main()
