"""TDD tests for handoff_extractor.py (stub module for step-7).

This file covers the stub behavior only.
The full 4-branch test suite (find one / find last of many / not found / JSON corrupt)
is step-9b's scope.

For this step:
  - The stub extract_handoff() must return MISSING_HANDOFF_PLACEHOLDER on any input.
"""

from __future__ import annotations

from handoff_extractor import extract_handoff
from plan_md_to_json import MISSING_HANDOFF_PLACEHOLDER


class TestExtractHandoffStub:
    """Verify the stub module ships green and returns the placeholder on all inputs."""

    def test_returns_placeholder_on_empty_string(self) -> None:
        result = extract_handoff("")
        assert result == MISSING_HANDOFF_PLACEHOLDER

    def test_returns_placeholder_on_arbitrary_jsonl(self) -> None:
        jsonl = '{"type":"assistant","message":{"content":[{"type":"text","text":"Done."}]}}\n'
        result = extract_handoff(jsonl)
        assert result == MISSING_HANDOFF_PLACEHOLDER

    def test_returns_placeholder_even_when_handoff_block_present(self) -> None:
        """Stub does NOT parse HANDOFF blocks — that is step-9's job."""
        jsonl = (
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"<handoff>{\\"scope\\":\\"test\\"}</handoff>"}]}}\n'
        )
        result = extract_handoff(jsonl)
        assert result == MISSING_HANDOFF_PLACEHOLDER

    def test_return_type_is_str(self) -> None:
        result = extract_handoff("anything")
        assert isinstance(result, str)
