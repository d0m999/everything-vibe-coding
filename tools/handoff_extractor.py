"""HANDOFF block extraction from stream-json JSONL output.

Public API
----------
extract_handoff(jsonl_text: str) -> str
    Scan a stream-json JSONL transcript and return the last <handoff>...</handoff>
    block found across all assistant turns.

    Returns MISSING_HANDOFF_PLACEHOLDER when no block is found or on any parse
    error (malformed JSON line, invalid JSON inside the tag, etc.).
"""

from __future__ import annotations

import json
import re

from plan_md_to_json import MISSING_HANDOFF_PLACEHOLDER


def extract_handoff(jsonl_text: str) -> str:
    """Extract the last <handoff>...</handoff> block from a stream-json transcript.

    Parameters
    ----------
    jsonl_text:
        Full stdout of a ``claude -p --output-format stream-json`` invocation,
        one JSON event per line.

    Returns
    -------
    str
        The compactly re-serialized JSON string inside the last
        ``<handoff>...</handoff>`` block found across ALL ``type=assistant``
        events, or ``MISSING_HANDOFF_PLACEHOLDER`` if no block is found or any
        parse error occurs.

    Algorithm
    ---------
    1. Split on newlines; skip blank lines.
    2. ``json.loads`` each line; skip lines that raise ``json.JSONDecodeError``.
    3. Keep only events whose top-level ``type == "assistant"``.
    4. From each assistant event walk ``message.content[*]`` items whose
       ``type == "text"`` and collect their ``text`` field.
    5. Concatenate all collected text fragments (in order) into one string so
       that regex matching spans assistant turns.
    6. ``re.findall(r"<handoff>(.*?)</handoff>", combined, re.DOTALL)`` —
       ``re.DOTALL`` is required so newlines inside the block are matched.
    7. Take the LAST match; if no matches return ``MISSING_HANDOFF_PLACEHOLDER``.
    8. ``json.loads(last_match.strip())`` — on ``json.JSONDecodeError`` return
       ``MISSING_HANDOFF_PLACEHOLDER``; on success return
       ``json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))``
       (compact single-line-ish form; preserves Unicode).
    """
    text_fragments: list[str] = []

    for line in jsonl_text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") != "assistant":
            continue

        for item in event.get("message", {}).get("content", []):
            if item.get("type") == "text":
                fragment = item.get("text", "")
                if fragment:
                    text_fragments.append(fragment)

    combined = "".join(text_fragments)
    matches = re.findall(r"<handoff>(.*?)</handoff>", combined, re.DOTALL)

    if not matches:
        return MISSING_HANDOFF_PLACEHOLDER

    last_match = matches[-1]
    try:
        parsed = json.loads(last_match.strip())
    except json.JSONDecodeError:
        return MISSING_HANDOFF_PLACEHOLDER

    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
