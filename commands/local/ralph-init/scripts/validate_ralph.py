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


def warn(message: str) -> None:
    print(f"WARN: {message}")


def main() -> None:
    if len(sys.argv) != 2:
        fail(
            "usage: validate_ralph.py <path-to-ralph.sh>",
            fix="pass exactly one path argument",
            example_valid="python3 validate_ralph.py ralph.sh",
        )

    path = Path(sys.argv[1])
    if not path.exists():
        fail(
            f"file not found: {path}",
            fix="generate ralph.sh first, or double-check the path",
        )

    text = path.read_text()
    lines = text.splitlines()

    # Strip shell comments (# ...) before pattern matching so commented-out
    # mechanisms don't count as real ones. We keep `text` intact for the
    # existing line-based checks; `code` is used for mechanism detection.
    code_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            continue
        if "#" in line:
            in_single = False
            in_double = False
            cut_at = None
            for i, ch in enumerate(line):
                if ch == "'" and not in_double:
                    in_single = not in_single
                elif ch == '"' and not in_single:
                    in_double = not in_double
                elif ch == "#" and not in_single and not in_double:
                    if i == 0 or line[i - 1] in " \t":
                        cut_at = i
                        break
            if cut_at is not None:
                line = line[:cut_at]
        code_lines.append(line)
    code = "\n".join(code_lines)

    required_snippets = [
        "current_story.json",
        "--print",
        "--dangerously-skip-permissions",
        "CLAUDE_EXIT_CODE",
        "YIELD",
        "COMPLETE",
        "VIOLATION",
        "prd.json",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        fail(
            f"missing required snippets: {missing}",
            why="these are the minimum signals the harness exchanges with the agent; "
                "missing any one of them breaks the feedback loop",
            fix="see references/output-contracts.md §ralph.sh for the full required mechanisms",
        )

    forbidden_snippets = [
        "timeout ",
        "claude -p ",
        "|| echo 0",
        "declare -A",
    ]
    found_forbidden = [snippet for snippet in forbidden_snippets if snippet in text]
    if found_forbidden:
        fail(
            f"found forbidden snippets: {found_forbidden}",
            why=(
                "`timeout` is not available on macOS by default; "
                "`claude -p` has been deprecated in favor of `--print`; "
                "`|| echo 0` masks real failures; "
                "`declare -A` requires bash 4+ which macOS does not ship"
            ),
            fix="use `claude --print`; drop `timeout`; replace `declare -A` with file-based tracker in `$RALPH_DIR/.retries/`",
            example_invalid=str(found_forbidden),
        )

    # `|| true` is forbidden near critical commands (claude, python3, git commit)
    # but allowed for defensive git stash/checkout in branch protection blocks.
    for i, line in enumerate(lines, 1):
        if "|| true" in line:
            stripped = line.strip()
            if any(cmd in stripped for cmd in ("claude", "python3", "git commit", "git push")):
                fail(
                    f"line {i}: `|| true` suppresses failure on critical command: {stripped}",
                    why="silently swallowing errors from claude/python3/git makes the loop report success when it actually failed",
                    fix="remove the `|| true` and let the command fail; "
                        "use `set +e` / `CLAUDE_EXIT_CODE=$?` / `set -e` if you need to inspect the code",
                )

    # Branch protection: harness must verify it's on the correct branch.
    has_branch_check = bool(re.search(r"git\s+branch\s+--show-current", text))
    if not has_branch_check:
        fail(
            "no branch check found; harness must verify it's on the target branch",
            why="if the agent silently switches branches, prd.json state diverges from main and VIOLATION fires on unrelated stories",
            fix="add a startup hard gate and an in-loop assertion using `git branch --show-current`",
            example_valid='if [ "$(git branch --show-current)" != "main" ]; then exit 1; fi',
        )

    # Structural diff check
    has_snapshot = bool(re.search(r"(before|prev|pre)[_\s]*(prd|passes|snapshot)", text, re.IGNORECASE))
    if not has_snapshot:
        fail(
            "no pre-iteration prd/passes snapshot found (need before-vs-after structural diff)",
            why="without a before/after snapshot the harness can't prove the agent touched only the locked story",
            fix="capture `pre_passes` before calling claude and compare with `post_passes` after",
            example_valid='pre_passes=$(python3 -c "... print passes states ...")',
        )

    if "passes" not in text:
        fail(
            "ralph.sh never references `passes`; structural diff cannot be enforced",
            fix='compare `pre_passes` vs `post_passes` and bail to VIOLATION on unexpected change',
        )

    passes_lines = [i for i, line in enumerate(lines) if "passes" in line]
    violation_lines = [i for i, line in enumerate(lines) if "VIOLATION" in line]
    linked = any(
        abs(p - v) <= 40 for p in passes_lines for v in violation_lines
    )
    if not linked:
        fail(
            "VIOLATION branch is not co-located with any `passes` check (structural diff not wired)",
            why="printing 'VIOLATION' without comparing passes doesn't actually prevent cross-story edits",
            fix="move the VIOLATION exit inside the same block that compares pre_passes vs post_passes (within ~40 lines)",
        )

    # --- NEW: Instance lock (borrowed from ralph-loop stop-hook.sh session_id pattern) ---
    # ralph.sh often runs for hours; two racing instances on the same .ralph/ dir
    # will corrupt each other's current_story.json. Require a PID-based lock.
    has_instance_lock_path = ".ralph/.instance" in code or "INSTANCE_LOCK" in code
    has_liveness_check = "kill -0" in code
    has_trap_cleanup = bool(re.search(r"trap\s+.*rm\s+.*EXIT", code))
    if not (has_instance_lock_path and has_liveness_check and has_trap_cleanup):
        missing_parts = []
        if not has_instance_lock_path:
            missing_parts.append("`.ralph/.instance` or `INSTANCE_LOCK` path")
        if not has_liveness_check:
            missing_parts.append("`kill -0 <pid>` liveness probe")
        if not has_trap_cleanup:
            missing_parts.append("`trap '... rm ... ' EXIT` cleanup")
        fail(
            f"instance lock incomplete; missing: {missing_parts}",
            why="two ralph.sh processes on the same .ralph/ dir corrupt each other's "
                "current_story.json. The ralph-loop plugin solves this via session_id "
                "check; the bash equivalent is a PID file + kill -0 liveness probe.",
            fix="write `$$:$(date +%s)` to .ralph/.instance at startup; "
                "refuse to start if an existing pid is still alive; "
                "trap EXIT to clean up",
            example_valid=(
                'INSTANCE_LOCK=".ralph/.instance"; '
                'if [ -f "$INSTANCE_LOCK" ]; then '
                'other=$(cut -d: -f1 "$INSTANCE_LOCK"); '
                'kill -0 "$other" 2>/dev/null && exit 1; fi; '
                'echo "$$:$(date +%s)" > "$INSTANCE_LOCK"; '
                "trap 'rm -f \"$INSTANCE_LOCK\"' EXIT"
            ),
        )

    # --- NEW: Atomic state writes ---
    # Any direct `>` redirect into current_story.json races with Ctrl+C and crashes.
    # Require temp-file + mv pattern somewhere touching state files.
    direct_state_write = re.search(
        r"^\s*[^#\n]*>\s*[\"']?[^\"'\n]*current_story\.json",
        code,
        re.MULTILINE,
    )
    has_atomic_pattern = bool(re.search(r"\.tmp(\.\$\$)?", code)) and "mv " in code
    if direct_state_write and not has_atomic_pattern:
        fail(
            "state file written non-atomically",
            why="a direct `> current_story.json` can leave the file half-written if "
                "ralph.sh is Ctrl+C'd mid-iteration. Next iteration reads garbage.",
            fix="write to `${target}.tmp.$$` then `mv` to the final path; "
                "mv is atomic on same filesystem",
            example_valid=(
                'tmp="$LOCK_FILE.tmp.$$"; '
                'echo "{\\"id\\": \\"$locked_id\\"}" > "$tmp"; '
                'mv "$tmp" "$LOCK_FILE"'
            ),
            example_invalid='echo "{\\"id\\": \\"$locked_id\\"}" > "$LOCK_FILE"',
        )
    if not has_atomic_pattern:
        fail(
            "no atomic write pattern found",
            why="any state file written to `.ralph/` must use temp+mv to survive Ctrl+C. "
                "Even if the current script doesn't write much, adding the helper prevents "
                "future regressions.",
            fix='define `atomic_write()` that writes to `.tmp.$$` then `mv` to target',
            example_valid=(
                'atomic_write() { local t="$1.tmp.$$"; printf "%s" "$2" > "$t"; mv "$t" "$1"; }'
            ),
        )

    # --- NEW: Numeric guard ---
    # Any numeric read from a file/exit-code should be regex-validated before use.
    # Require either a helper function or an inline regex pattern guard.
    has_nonneg_helper = "assert_nonneg_int" in code
    has_inline_numeric_guard = bool(re.search(r"=~\s*\^\[0-9\]\+\$", code))
    if not (has_nonneg_helper or has_inline_numeric_guard):
        fail(
            "no numeric guard helper or inline `^[0-9]+$` check found",
            why="retry counters, exit codes, and iteration numbers must be regex-validated "
                "before `$((...))` arithmetic. Corrupt state files are a common failure mode "
                "(see references/incidents.md).",
            fix="define `assert_nonneg_int()` and call it on every numeric you read from state; "
                "the helper can be preemptively present even if not used yet",
            example_valid=(
                'assert_nonneg_int() { '
                'if ! [[ "$2" =~ ^[0-9]+$ ]]; then echo "FATAL: $1 not int"; exit 1; fi; }'
            ),
        )

    print(f"OK: {path} validated")


if __name__ == "__main__":
    main()
