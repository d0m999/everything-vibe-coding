---
name: mempaw-loop-status
description: Report a compact status summary for a run started by /mempaw-loop-start, without pulling the run's full log or subprocess transcript into this session's context.
---

# mempaw-loop-status

Summarize the state of a `long-agent-loop` canonical run started by
`/mempaw-loop-start`. This command reads small, bounded artifacts (JSON state
files, the last ~20 log lines) — never the full log, never a `claude -p`
subprocess transcript. If you find yourself about to `cat`/`tail -f` a whole
log file, stop: that defeats the point of this command.

## Usage

`/mempaw-loop-status [run_id]`

## Steps

1. **Resolve the run.** If `run_id` was given in `$ARGUMENTS`, read
   `~/.claude/state/mempaw-loop/<run_id>.json`. Otherwise read
   `~/.claude/state/mempaw-loop/latest.json`. If neither exists, list
   `~/.claude/state/mempaw-loop/*.json` and ask the user which run they mean.

2. **Locate on-disk state** under the target repo, using `project_root`,
   `base`, `slug`, and `isolate` from the registry:
   - If `isolate` is true: read the main-side pointer
     `<project_root>/.work/worktrees/<slug>-<slugified-base>.json` for its
     `worktree_path` field. State root is `<worktree_path>/.work`. If the
     pointer is gone (worktree already cleaned up after a terminal
     success), fall back to `<project_root>/.work` directly — the worktree
     may have been removed once its commits landed on the pushed branch.
   - Else: state root is `<project_root>/.work`.
   - `<slugified-base>` uses the same slugify rule as the plan slug
     (lowercase, non-alphanumeric runs collapsed to `-`, trimmed).
   - **Resolve the authoritative engine pid:** Read `<state root>/run.lock`
     if it exists and is readable (JSON file written by the engine for the
     entire run duration). Extract the `pid` field from the lock — this is
     the real `workflow_runner.py` process, not the nohup wrapper. This
     deserves priority over the registry's `pid` field (which records only
     the wrapper's pid). If the lock file is absent or unreadable, fall back
     to the registry's `pid`. The lock is deleted by the engine on exit, so
     its absence is consistent with an already-finished run.
   - Deterministic step-state:
     `<state root>/loop-<slug>-<slugified-base>/state.json` and the sibling
     `canonical-meta.json` (branch name, base, per-step machine state:
     `pending` / `in_progress` / `committed` / `review_passed`).
   - Newest `<state root>/canonical-*/ledger.json` (by mtime) for
     confirmed-findings counts and dispositions (`false_positive` /
     `wontfix` / etc).
   - Newest `<state root>/canonical-*/summary.json` (by mtime) if present.
   - If `slug` in the registry is empty (best-effort computation failed at
     start time), skip the deterministic path and just glob
     `<state root>/loop-*/state.json` and `<state root>/canonical-*/` by
     mtime instead.

3. **Liveness.** `kill -0 <pid> 2>/dev/null` using the authoritative `pid`
   resolved in step 2. Separately check whether `<exit_file>` exists — its
   presence is the authoritative "finished" signal (a PID can be recycled by
   the OS after exit, so PID-absence alone is not proof of anything). If
   `exit_file` exists, read the integer inside it and map it via the
   canonical exit-code table:
   - `0` → `pr_opened` / `pushed_no_pr`
   - `1` → `review_blocked@step-N` / `budget_exhausted@step-N`
   - `2` → `execute_failed` / `review_unavailable` / `review_errored` /
     `push_failed` / `pointer_exists` / `locked`
   - `3` → `needs_plan_approval` (should not occur on the canonical path)

   `pushed_no_pr` is ambiguous by itself — it covers two different cases
   distinguished by the ledger's `push_status` field: `push_status: "skipped"`
   means this was a `--no-push` dry run (nothing touched the remote — verify
   with `git -C <project_root> ls-remote --heads <remote> <branch>` if you
   need certainty); `push_status: "pushed"` means a real push happened but
   `gh` was missing (benign).

4. **Bounded log peek.** `tail -n 20 <log_file>` — only as a secondary "what
   is it doing right now" signal, never the full file.

5. **Compose ONE reply** with: run_id · target repo · branch · live/finished
   (+ exit-code meaning if finished) · current step + its state-machine
   phase · latest step commit sha · ledger finding counts/dispositions ·
   trimmed last log lines. If finished with a terminal status, name the next
   human action (merge the PR / inspect `ledger.json` / re-run with
   `--resume`).

   **Worktree cleanup (dry-run runs only):** `run_isolated` only removes the
   worktree/pointer when `push_status == "pushed"` — a `--no-push` dry run
   *always* leaves the worktree and its local `loop/<slug>-<ts>` branch on
   disk (by design, so you can inspect it), even on a clean `exit_code=0`.
   Mention this in the reply so the user isn't surprised the worktree is
   still there, and offer `--prune-worktrees` if they want it gone.

   **Kill a runaway/stuck run:** If the run is still `live` and needs to be
   terminated:
   - **If the registry has a `pgid` field** (new runs, post-July-2026): the
     safe way to kill the ENTIRE run including any in-flight `claude -p`
     grandchild subprocesses is `kill -- -$PGID` — the leading `--` is
     mandatory (otherwise a negative argument like `-12345` is parsed as an
     option), and killing by negative pgid terminates the whole process
     group at once.
   - **If the registry predates the `pgid` field** (older runs): degrade
     gracefully — kill just the recorded wrapper `pid` (plain `kill <pid>`,
     no dash/group syntax) and warn the user that any already-spawned `claude
     -p` grandchild processes may be left running as orphans and may need
     manual cleanup (`ps` for the workflow_runner process tree).
   - Never guess or invent a pgid if the field is absent — that risks killing
     an unrelated, PID-recycled process group.

## Arguments

$ARGUMENTS:
- `[run_id]` optional — defaults to the most recently started run
