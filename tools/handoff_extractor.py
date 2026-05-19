"""Stub module for HANDOFF block extraction from stream-json JSONL output.

Public API
----------
extract_handoff(jsonl_text: str) -> str
    Scan a stream-json JSONL transcript and return the last <handoff>...</handoff>
    block found across all assistant turns.

    Returns MISSING_HANDOFF_PLACEHOLDER when no block is found (or on parse error).

Implementation status
---------------------
This module is a STUB for step-7.  The function signature is final; the real
extraction logic (scan all assistant turns, regex for last <handoff> block,
JSON-decode, fallback on error) is implemented in step-9.

Until step-9 lands, extract_handoff() always returns MISSING_HANDOFF_PLACEHOLDER.
This is correct: step-7 does not splice HANDOFF between agents — each agent
receives its prompt verbatim from the JSON.
"""

from __future__ import annotations

from plan_md_to_json import MISSING_HANDOFF_PLACEHOLDER


def extract_handoff(jsonl_text: str) -> str:  # noqa: ARG001
    """Extract the last <handoff>...</handoff> block from a stream-json transcript.

    Parameters
    ----------
    jsonl_text:
        Full stdout of a ``claude -p --output-format stream-json`` invocation,
        one JSON event per line.

    Returns
    -------
    str
        The JSON string inside the last ``<handoff>...</handoff>`` block found
        across all ``type=assistant`` events, or ``MISSING_HANDOFF_PLACEHOLDER``
        if no block is found or any parse error occurs.

    Notes
    -----
    STUB — step-9 will implement the real extraction logic:
    1. Parse each line as JSON.
    2. Filter ``type == "assistant"`` events.
    3. Scan ``message.content[*].text`` for ``<handoff>...</handoff>``.
    4. Return the LAST match; fall back to MISSING_HANDOFF_PLACEHOLDER.
    """
    # TODO(step-9): implement real extraction — scan jsonl_text line by line,
    # filter type=assistant events, collect all <handoff>...</handoff> regex
    # matches from message.content[*].text, return the last one.
    # For now, always return the placeholder so step-7 ships green.
    return MISSING_HANDOFF_PLACEHOLDER
