#!/usr/bin/env python3

import re
import sys
from pathlib import Path


def fail(message: str, *, why: str | None = None, fix: str | None = None,
         example_valid: str | None = None, example_invalid: str | None = None) -> None:
    print(f"FAIL: {message}")
    if why:
        print(f"  Why: {why}")
    if fix:
        print(f"  Fix: {fix}")
    if example_valid:
        print(f"  Valid example: {example_valid}")
    if example_invalid:
        print(f"  Invalid example: {example_invalid}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail(
            "usage: validate_prompt.py <path-to-PROMPT.md>",
            fix="pass exactly one path argument",
            example_valid="python3 validate_prompt.py .ralph/PROMPT.md",
        )

    path = Path(sys.argv[1])
    if not path.exists():
        fail(
            f"file not found: {path}",
            fix="generate .ralph/PROMPT.md first, or double-check the path",
        )

    text = path.read_text()
    text_lower = text.lower()

    forbidden_templates = [
        "{story}",
        "{stories}",
        "{model}",
        "{pattern}",
        "{patterns}",
        "{prd}",
        "{plan}",
        "{plans}",
        "{project}",
        "{branch}",
        "{progress}",
    ]
    for token in forbidden_templates:
        if token in text:
            fail(
                f"template variable detected: {token}",
                why="PROMPT.md is piped to `claude --print` via stdin — no template engine runs against it. "
                    "Literal `{story}` etc. will reach the agent unresolved.",
                fix="rewrite the occurrence as 'read field X from .ralph/<file>'",
                example_valid="read the `id` field from `.ralph/current_story.json`",
                example_invalid=token,
            )

    double_brace = re.search(r"\{\{[^}\n]{1,80}\}\}", text)
    if double_brace:
        fail(
            f"template variable detected: {double_brace.group(0)}",
            why="Jinja/Mustache-style `{{...}}` will reach the agent unresolved",
            fix="replace with 'read from .ralph/<file>' instructions",
            example_invalid=double_brace.group(0),
        )

    required_snippets = [
        ".ralph/current_story.json",
        ".ralph/progress.txt",
        ".ralph/prd.json",
        "<promise>YIELD</promise>",
        "<promise>COMPLETE</promise>",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        fail(
            f"missing required snippets: {missing}",
            why="PROMPT.md must reference every file the agent reads and the two promise tags the harness checks",
            fix="add instructions that mention each missing string verbatim",
            example_valid="Step 0: read `.ralph/current_story.json` to find the locked story id.",
        )

    # --- Anti-cheat integrity block (borrowed from ralph-loop setup script) ---
    # Require both an "unequivocally true" style claim AND an explicit "don't lie" clause,
    # both near the COMPLETE promise. This defends against agents emitting a premature
    # COMPLETE just to escape the loop.
    truth_phrases = [
        "unequivocally true",
        "genuinely true",
        "completely and unequivocally",
    ]
    honesty_phrases = [
        "do not output a false",
        "do not lie",
        "do not emit a false",
    ]

    has_truth = any(phrase in text_lower for phrase in truth_phrases)
    has_honesty = any(phrase in text_lower for phrase in honesty_phrases)

    if not has_truth:
        fail(
            "PROMPT.md is missing the completion-integrity truth claim",
            why="agents tend to output a premature <promise>COMPLETE</promise> to escape long loops. "
                "The prompt must explicitly require the promise to be true before emission.",
            fix=f"add a sentence containing one of: {truth_phrases}",
            example_valid=(
                "The `<promise>COMPLETE</promise>` statement MUST be completely and "
                "unequivocally true before you emit it."
            ),
        )

    if not has_honesty:
        fail(
            "PROMPT.md is missing the completion-integrity anti-lie clause",
            why="a truth claim without an anti-lie counterweight still leaves room for 'I think it's close enough'. "
                "An explicit prohibition works better than pure encouragement.",
            fix=f"add a sentence containing one of: {honesty_phrases}",
            example_valid=(
                "Do not output a false promise to exit the loop. Do not lie even if you think "
                "you are stuck or the task is impossible."
            ),
        )

    print(f"OK: {path} validated")


if __name__ == "__main__":
    main()
