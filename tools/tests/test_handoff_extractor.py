"""7-test suite for handoff_extractor.extract_handoff() (5 spec branches + 2 robustness).

Coverage targets
----------------
1. test_extract_returns_handoff_when_present
   Single <handoff> block in one assistant turn — happy path.

2. test_extract_returns_last_when_multiple
   Multiple <handoff> blocks across DIFFERENT assistant turns — last wins.

3. test_extract_returns_placeholder_when_absent
   Assistant turns exist but carry no <handoff> tag at all.

4. test_extract_returns_placeholder_when_json_broken
   A <handoff> tag is present but its body is not valid JSON.

5. test_extract_scans_all_assistant_turns_not_only_final
   REGRESSION GUARD: the LAST assistant turn says only "Done." (no handoff);
   the MIDDLE turn carries the only <handoff> block — it must still be found.

Fixture style
-------------
Each JSONL line is a full stream-json event object with realistic fields:
  type, uuid, session_id, parent_tool_use_id, message (role + content list).
Non-assistant event types (user, tool_result, result) are mixed in so the
filter logic is exercised.  Helper builders keep test bodies concise.
"""

from __future__ import annotations

import json
import uuid as _uuid_mod

from handoff_extractor import extract_handoff
from plan_md_to_json import MISSING_HANDOFF_PLACEHOLDER

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SESSION_A = "sess-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_SESSION_B = "sess-b9e8d7c6-f5a4-3210-fedc-ba9876543210"


def _assistant_event(
    text: str,
    *,
    uuid_str: str | None = None,
    session_id: str = _SESSION_A,
) -> str:
    """Return a single stream-json line for an assistant text event."""
    return json.dumps(
        {
            "type": "assistant",
            "uuid": uuid_str or str(_uuid_mod.uuid4()),
            "session_id": session_id,
            "parent_tool_use_id": None,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }
    )


def _user_event(text: str, *, session_id: str = _SESSION_A) -> str:
    """Return a single stream-json line for a user message event."""
    return json.dumps(
        {
            "type": "user",
            "uuid": str(_uuid_mod.uuid4()),
            "session_id": session_id,
            "parent_tool_use_id": None,
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": text}],
            },
        }
    )


def _tool_result_event(tool_use_id: str, output: str, *, session_id: str = _SESSION_A) -> str:
    """Return a single stream-json line for a tool_result event."""
    return json.dumps(
        {
            "type": "tool_result",
            "uuid": str(_uuid_mod.uuid4()),
            "session_id": session_id,
            "parent_tool_use_id": tool_use_id,
            "message": {
                "role": "tool",
                "content": [{"type": "text", "text": output}],
            },
        }
    )


def _result_event(subtype: str = "success", *, session_id: str = _SESSION_A) -> str:
    """Return a single stream-json line for a result/completion event."""
    return json.dumps(
        {
            "type": "result",
            "uuid": str(_uuid_mod.uuid4()),
            "session_id": session_id,
            "parent_tool_use_id": None,
            "subtype": subtype,
            "duration_ms": 1234,
        }
    )


def _build_jsonl(*lines: str) -> str:
    """Join event lines into a single JSONL string."""
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractHandoff:
    """Full coverage of extract_handoff(): 5 spec branches + 2 extra robustness tests."""

    # ------------------------------------------------------------------
    # Branch 1 — single handoff block present
    # ------------------------------------------------------------------

    def test_extract_returns_handoff_when_present(self) -> None:
        """Single <handoff> block in one assistant turn returns parsed content."""
        expected = {
            "scope": "step-9b implementation",
            "status": "done",
            "next": "code-review",
        }
        handoff_body = json.dumps(expected)
        jsonl = _build_jsonl(
            _user_event("implement handoff extractor"),
            _tool_result_event("tid-001", "read 87 lines"),
            _assistant_event(f"Implementation complete.\n<handoff>{handoff_body}</handoff>"),
            _result_event("success"),
        )

        result = extract_handoff(jsonl)

        parsed = json.loads(result)
        assert parsed == expected

    # ------------------------------------------------------------------
    # Branch 2 — multiple handoff blocks across different assistant turns
    # ------------------------------------------------------------------

    def test_extract_returns_last_when_multiple(self) -> None:
        """When multiple <handoff> blocks appear in different turns, the last wins."""
        first_payload = {"scope": "step-9", "status": "partial"}
        last_payload = {"scope": "step-9b", "status": "complete", "coverage": 97}

        jsonl = _build_jsonl(
            _user_event("start task"),
            _assistant_event(
                f"Checkpoint reached.\n<handoff>{json.dumps(first_payload)}</handoff>",
                uuid_str="uuid-turn-01",
            ),
            _user_event("continue"),
            _tool_result_event("tid-002", "wrote tests"),
            _assistant_event(
                f"All done.\n<handoff>{json.dumps(last_payload)}</handoff>",
                uuid_str="uuid-turn-02",
                session_id=_SESSION_B,
            ),
            _result_event("success", session_id=_SESSION_B),
        )

        result = extract_handoff(jsonl)

        parsed = json.loads(result)
        assert parsed == last_payload

    # ------------------------------------------------------------------
    # Branch 3 — no handoff tag anywhere
    # ------------------------------------------------------------------

    def test_extract_returns_placeholder_when_absent(self) -> None:
        """When assistant turns contain no <handoff> tag, placeholder is returned."""
        jsonl = _build_jsonl(
            _user_event("summarise file"),
            _assistant_event("The file has 87 lines and exports extract_handoff()."),
            _assistant_event("Let me know if you need anything else."),
            _result_event("success"),
        )

        result = extract_handoff(jsonl)

        assert result == MISSING_HANDOFF_PLACEHOLDER

    # ------------------------------------------------------------------
    # Branch 4 — handoff tag present but body is invalid JSON
    # ------------------------------------------------------------------

    def test_extract_returns_placeholder_when_json_broken(self) -> None:
        """Malformed JSON inside <handoff> tag triggers placeholder fallback."""
        jsonl = _build_jsonl(
            _user_event("run step"),
            _assistant_event("Attempted summary.\n<handoff>not valid json at all {</handoff>"),
            _result_event("error"),
        )

        result = extract_handoff(jsonl)

        assert result == MISSING_HANDOFF_PLACEHOLDER

    # ------------------------------------------------------------------
    # Extra branch — blank lines in JSONL are silently skipped
    # ------------------------------------------------------------------

    def test_extract_tolerates_blank_lines_in_jsonl(self) -> None:
        """Blank lines between JSONL events must be ignored, not crash."""
        payload = {"scope": "blank-line-test"}
        # Intentionally embed multiple blank lines between events.
        jsonl = (
            _user_event("go") + "\n"
            "\n"
            "\n"
            + _assistant_event(f"<handoff>{json.dumps(payload)}</handoff>")
            + "\n"
            "\n"
        )

        result = extract_handoff(jsonl)

        parsed = json.loads(result)
        assert parsed == payload

    # ------------------------------------------------------------------
    # Extra branch — non-JSON garbage lines are silently skipped
    # ------------------------------------------------------------------

    def test_extract_tolerates_non_json_lines(self) -> None:
        """Lines that are not valid JSON must be ignored without raising."""
        payload = {"scope": "nonjson-line-test"}
        jsonl = (
            "this is not json at all\n"
            "---\n"
            + _assistant_event(f"<handoff>{json.dumps(payload)}</handoff>")
            + "\n"
            "} broken { garbage\n"
        )

        result = extract_handoff(jsonl)

        parsed = json.loads(result)
        assert parsed == payload

    # ------------------------------------------------------------------
    # Branch 5 — REGRESSION GUARD: handoff in middle turn, last turn is bare
    # ------------------------------------------------------------------

    def test_extract_scans_all_assistant_turns_not_only_final(self) -> None:
        """Handoff in a middle assistant turn is extracted even when the final
        assistant turn carries no <handoff> tag.

        This guards against an implementation that only inspects the last turn.
        The fixture contains:
          - turn 1: assistant says something intro (no handoff)
          - turn 2: assistant carries the only <handoff> block
          - turn 3: assistant says "Done." only (no handoff)
        """
        middle_payload = {
            "scope": "step-9b-regression",
            "output_file": "tests/test_handoff_extractor.py",
            "risks": ["none identified"],
        }

        jsonl = _build_jsonl(
            _user_event("begin"),
            # Turn 1 — no handoff
            _assistant_event(
                "Starting analysis of the implementation.",
                uuid_str="uuid-turn-a",
            ),
            _tool_result_event("tid-010", "file read successfully"),
            # Turn 2 — carries the only handoff block
            _assistant_event(
                "Analysis complete. Proceeding to write tests.\n"
                f"<handoff>{json.dumps(middle_payload)}</handoff>",
                uuid_str="uuid-turn-b",
            ),
            _user_event("carry on"),
            # Turn 3 — final turn, no handoff tag
            _assistant_event(
                "Done.",
                uuid_str="uuid-turn-c",
                session_id=_SESSION_B,
            ),
            _result_event("success", session_id=_SESSION_B),
        )

        result = extract_handoff(jsonl)

        parsed = json.loads(result)
        assert parsed == middle_payload
