---
name: mempaw-loop-start
description: Launch a long-agent-loop canonical run against a target project as a detached background process, so this Claude Code session never absorbs the execution engine's stdout/context. Pair with /mempaw-loop-status.
disable-model-invocation: true
---

# mempaw-loop-start

Start `long-agent-loop`'s canonical feature-branch driver
(`workflow_runner.py --canonical`) against a target project, fully detached
from this Claude Code session's process group. This command must return in a
few seconds — it never waits for the canonical run to finish, and it never
tails the run's log into the conversation.

The long-agent-loop toolchain itself always lives at
`~/Desktop/long-agent-loop` (hardcoded — it is a fixed local install, not
per-target). All git side effects (branch, commits, push, PR) happen inside
`--project-root`, which is a *different* repository.

## Usage

`/mempaw-loop-start --project-root <path> --plan-json <path> [--base <branch>] (--max-wall-clock-s <seconds> | --max-total-invocations <n>) [--no-isolate] [--push] [--resume] [flags...]`

## Preflight (fail loud — do not launch on a violation)

1. Resolve `--project-root` and `--plan-json` to absolute paths. Refuse if
   either is missing from `$ARGUMENTS`, or if `--plan-json` does not exist on
   disk.
2. `--project-root` must be a git repo:
   `git -C <project-root> rev-parse --is-inside-work-tree`.
3. Tree cleanliness — **only when `--no-isolate` was passed**: on a
   non-isolated run, `run_canonical` operates directly on `--project-root`,
   so `git -C <project-root> status --porcelain` must be empty (tracked
   *and* untracked files both count); a fresh non-isolated run fails loud on
   a dirty tree anyway, so catch it here with a clear message instead of
   letting the backgrounded process die silently after you've already
   detached it. **Skip this check entirely when `--isolate` is in effect
   (the default)** — isolation runs inside a freshly `git worktree add
   --detach`'d checkout of `--base`, which starts clean regardless of the
   main checkout's state; requiring the main checkout to be clean here
   would be over-conservative and block a legitimate isolated run for no
   reason (the operator's own working changes on `--project-root` are none
   of this command's business when isolated). If dirty and `--no-isolate`,
   stop and tell the user which paths are dirty; only `--resume` may
   tolerate residue, and only on the branch being recovered.
4. Budget: require at least one of `--max-wall-clock-s` /
   `--max-total-invocations` in `$ARGUMENTS`. If neither is present, stop and
   ask the user for one — never invent a default number silently (mirrors
   the tool's own `BudgetRequiredError` contract).
5. Base branch: isolation (`--isolate`, the default — see below) requires an
   explicit `--base` naming a *real local branch* in `--project-root`:
   `git -C <project-root> show-ref --verify --quiet refs/heads/<base>`.
   If `--base` was omitted, try
   `git -C <project-root> branch --show-current` and use that; if that is
   also empty, stop and ask the user to supply `--base` explicitly.
6. Push/PR is a real, externally-visible side effect (branch push + `gh pr
   create` in the target repo). Default to **dry run** (`--no-push`) unless
   `$ARGUMENTS` contains `--push`. Before launching a non-dry-run (`--push`)
   run, show the user the exact command line you are about to background and
   get explicit confirmation in this chat turn first — the confirmation
   itself is cheap; only the multi-step *execution* is what must stay off
   this session's plate.

## Launch

```bash
mkdir -p ~/.claude/state/mempaw-loop
RUN_ID="$(basename "<project-root>")-$(date -u +%Y%m%dT%H%M%SZ)"
STATE_DIR="$HOME/.claude/state/mempaw-loop"
LOG="$STATE_DIR/$RUN_ID.log"
EXIT_FILE="$STATE_DIR/$RUN_ID.exit"
REGISTRY="$STATE_DIR/$RUN_ID.json"
PGID_FILE="$STATE_DIR/$RUN_ID.pgid"

cd ~/Desktop/long-agent-loop

# Best-effort plan slug so /mempaw-loop-status can find
# .work/loop-<slug>-<base-slug>/ deterministically later. Non-fatal if this
# fails — status falls back to scanning .work/ by mtime.
#
# MUST pass plan_json_path as derive_plan_slug's second positional arg (not
# just the title) to match run_canonical/run_isolated's own call exactly
# (workflow_runner.py:3250 / worktree_runner.py:173 both call
# derive_plan_slug(_read_plan_title(plan_json_path), plan_json_path)) — since
# WI-4 (slug anti-collision, already merged to main), the real engine
# appends a 12-hex path-hash suffix whenever plan_json_path is given. Omitting
# it here computes the OLD, unsuffixed slug, which then can never match the
# real worktree/pointer filename the engine actually creates — this silently
# broke every on-disk-state lookup in /mempaw-loop-status for isolated runs
# until caught by a real end-to-end smoke test (2026-07-04).
SLUG="$(.venv/bin/python -c '
from workflow_runner import derive_plan_slug, _read_plan_title
print(derive_plan_slug(_read_plan_title("<plan-json>"), "<plan-json>"))
' 2>/dev/null || true)"

MY_PGID="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"
rm -f "$PGID_FILE"

.venv/bin/python -c '
import os, sys
try:
    os.setsid()
except OSError:
    pass
with open(sys.argv[1], "w") as f:
    f.write(str(os.getpgrp()))
os.execvp("nohup", ["nohup", "bash", "-c", sys.argv[2]])
' "$PGID_FILE" '
  .venv/bin/python workflow_runner.py --canonical <isolate-flag> \
    --plan-json "<plan-json>" \
    --project-root "<project-root>" \
    --base "<base>" \
    <push-flag> <budget-flags> <passthrough-flags>
  echo $? > "'"$EXIT_FILE"'"
' > "$LOG" 2>&1 &
disown
PID=$!

# Wait for the wrapper to self-report its pgid (race-free by construction:
# the wrapper writes its OWN os.getpgrp() to PGID_FILE right after calling
# os.setsid(), so the file's presence is proof the value is already fixed —
# never an outside guess raced against fork/exec timing). Bounded to ~2s;
# if the file never appears, degrade to null rather than risk a wrong value.
PGID=""
for _ in $(seq 1 100); do
  if [ -s "$PGID_FILE" ]; then
    CANDIDATE="$(tr -d ' \n' < "$PGID_FILE" 2>/dev/null)"
    # Leaf defense-in-depth: never accept a pgid equal to our own — that
    # would mean detachment silently didn't happen, and a later group-kill
    # (mempaw-loop-status's "Kill a runaway/stuck run") must never be able
    # to target this session's own process group.
    if [ -n "$CANDIDATE" ] && [ "$CANDIDATE" != "$MY_PGID" ]; then
      PGID="$CANDIDATE"
    fi
    break
  fi
  sleep 0.02
done
rm -f "$PGID_FILE"
PGID_JSON="${PGID:-null}"

cat > "$REGISTRY" <<EOF
{
  "run_id": "$RUN_ID",
  "pid": $PID,
  "pgid": $PGID_JSON,
  "project_root": "<project-root>",
  "plan_json": "<plan-json>",
  "base": "<base>",
  "isolate": <true-or-false>,
  "push": <true-or-false>,
  "slug": "$SLUG",
  "log_file": "$LOG",
  "exit_file": "$EXIT_FILE",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
cp "$REGISTRY" "$STATE_DIR/latest.json"
```

**Why the Python `os.setsid()` wrapper:** The launch invocation detaches the
backgrounded job into its own session/process group before it executes, enabling
safe, group-wide termination via the `pgid` field later. The raw `setsid` command
from util-linux is not available on macOS (where this project's dev machine
runs); we use Python's standard library instead — no new external dependency,
since `.venv/bin/python` is already mandatory. The `try/except OSError` handles
the case where job control is enabled (bash already isolated the pgid) and
`os.setsid()` correctly fails — the pgid is already isolated regardless.

**Why the pgid is self-reported via `PGID_FILE`, not sampled with `ps -o pgid=
-p "$PID"` right after backgrounding:** an earlier version of this design did
exactly that, and it has a real race — empirically reproduced 20/20 times on
this exact machine. Right after `fork()`, the child's pgid still equals the
*caller's own* pgid until the child itself finishes running `os.setsid()`;
sampling from outside before that happens (which a bare `ps` right after `&` /
`disown` reliably does — the window is only ~10–30ms) silently records the
wrong value: the operator's *own* shell session's pgid. A later
`kill -- -$PGID` (see `/mempaw-loop-status`'s "Kill a runaway/stuck run") would
then target the operator's own shell, not the detached run — the exact
disaster this mechanism exists to prevent. The fix is for the Python wrapper to
report its *own*, self-observed `os.getpgrp()` into `PGID_FILE` itself,
immediately after the `os.setsid()` attempt — a self-attested value, never an
outside guess — and for the launcher to wait (bounded to ~2s) for that file
before trusting it. `MY_PGID` (the launcher's own pgid, captured before
backgrounding — no race, it is reading its own live state) is compared against
whatever is read back as one more leaf defense: an equal value is refused and
degrades to `null` rather than ever being written to the registry.

Substitute every `<...>` placeholder with the resolved/validated values before
running — do not leave literal angle brackets in the executed command.
`<isolate-flag>` is `--isolate` unless `--no-isolate` was passed.
`<push-flag>` is `--no-push` (default) unless `--push` was passed, in which
case omit it entirely. `<budget-flags>` / `<passthrough-flags>` are whatever
budget/tuning flags the user supplied verbatim (`--max-step-exec-iterations`,
`--max-step-review-iterations`, `--timeout-s`, `--stale-ttl-s`, `--remote`,
`--resume`, ...).

## Report back

Reply with: `run_id`, `pid`, the `log_file` path, whether this is a dry run
or a real push/PR run, and a reminder that the way to check on it is
`/mempaw-loop-status [run_id]` — **not** `tail -f` / `cat` on the log file in
this session, which is exactly the context-blowup this command exists to
avoid.

If this is a `--no-push` dry run (the default): **important note** — even on
full success, the worktree and its local `loop/<slug>-<ts>` branch are
intentionally kept on disk (P4 worktree-isolation design, so you can inspect
them). To clean them up when done: `--prune-worktrees` or manual `git worktree
remove <path>` + `git branch -d <branch>`.

## Arguments

$ARGUMENTS:
- `--project-root <path>` required
- `--plan-json <path>` required
- `--base <branch>` optional (auto-detected from the target repo's current
  branch if omitted; still required to resolve to a real local branch)
- `--max-wall-clock-s <seconds>` / `--max-total-invocations <n>` — at least
  one required
- `--no-isolate` optional (default: run inside a `git worktree`, main
  checkout stays clean)
- `--push` optional (default: `--no-push` dry run; only pushes/opens a PR
  when explicitly given, after confirmation)
- `--resume` optional
- any other pass-through flag the canonical driver accepts
  (`--remote`, `--max-step-exec-iterations`, `--max-step-review-iterations`,
  `--timeout-s`, `--stale-ttl-s`)
