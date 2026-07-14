---
name: mempaw-loop-plan
description: Bridge a /plan-orchestrate markdown output (in this conversation, or saved to a file) into a validated plan.orchestrate.json ready for /mempaw-loop-start --plan-json, and suggest a --max-total-invocations budget derived from the plan's own agent-call count. Purely mechanical — no LLM generation happens inside this command.
---

# mempaw-loop-plan

Convert an already-generated `/plan-orchestrate` result into a parsed
`plan.orchestrate.json`. This command does **not** run `/plan-orchestrate`
itself and does not invoke any agent — it only saves/reads a markdown
document and runs the deterministic parser (`plan_md_to_json.parse_file`).
It should complete in a couple seconds.

The parser lives at `~/Desktop/long-agent-loop` (hardcoded, same fixed
install as `/mempaw-loop-start` / `/mempaw-loop-status`) and needs its own
`.venv/bin/python` (3.11+) regardless of which workspace this command is
invoked from.

## Usage

`/mempaw-loop-plan [--md <path>] [--out <path>]`

## Steps

1. **Get the source markdown.**
   - If `--md <path>` was given: read that file. Refuse if it does not exist
     or is empty.
   - Otherwise: look earlier in *this* conversation for the most recent
     `/plan-orchestrate` result — a document starting with
     `# Plan-Orchestrate Result` (or otherwise clearly the skill's output:
     overview table + parallel-execution graph + `## Step N — <title>`
     blocks with `em-dash`). Save that text **verbatim** to
     `~/.claude/state/mempaw-loop/plans/<UTC-timestamp>.orchestrate.md`
     (`mkdir -p` the `plans/` dir first). If no such output exists earlier
     in this conversation and `--md` was not given, stop and ask the user
     to either pass `--md <path>` or run `/plan-orchestrate` first — do not
     guess or fabricate a plan document.

2. **Decide the output JSON path.**
   - If `--out <path>` was given, use it verbatim.
   - Else, derive it from the source markdown path: replace a trailing
     `.md` with `.json` (or append `.json` if the source has no `.md`
     suffix). For a freshly-saved in-conversation source this naturally
     lands next to the `.md` file under
     `~/.claude/state/mempaw-loop/plans/`.

3. **Parse.** From `~/Desktop/long-agent-loop`, using its own venv:

   ```bash
   cd ~/Desktop/long-agent-loop
   .venv/bin/python -c "
   import json, sys
   from pathlib import Path
   from plan_md_to_json import parse_file
   try:
       plan = parse_file('<md-path>')
   except Exception as e:
       print(f'PARSE_ERROR: {type(e).__name__}: {e}', file=sys.stderr)
       sys.exit(1)
   Path('<out-path>').write_text(
       json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
   meta = plan.get('meta', {})
   print(f\"OK steps={len(plan.get('steps', []))} lang={meta.get('lang')} py_sub={meta.get('py_sub')}\")
   "
   ```

   Substitute `<md-path>` / `<out-path>` with the resolved absolute paths.
   A non-zero exit means `parse_file` raised — surface the `PARSE_ERROR`
   line verbatim to the user (e.g. a malformed `Acceptance-contract` line,
   a stray non-`Agent(...)` fence, a missing em-dash in a step header — see
   the parser-contract gotchas in `~/Desktop/long-agent-loop/CLAUDE.md` if
   the message alone isn't enough to diagnose). Do **not** leave a partial
   or empty JSON file behind on failure.

4. **Best-effort slug preview.** On a successful parse, also compute the
   slug `/mempaw-loop-start` will later derive for this same plan, so the
   user can already see the `.work/loop-<slug>-<base>/` name it will use:

   ```bash
   .venv/bin/python -c "
   from workflow_runner import derive_plan_slug, _read_plan_title
   print(derive_plan_slug(_read_plan_title('<out-path>')))
   " 2>/dev/null || true
   ```

   Non-fatal if this fails (best-effort only).

5. **Suggest a `--max-total-invocations` budget from the plan's own shape**
   (not a made-up constant — derived from how many agents this specific
   plan will actually invoke):

   ```bash
   .venv/bin/python -c "
   import json
   plan = json.load(open('<out-path>'))
   steps = plan.get('steps', [])
   total_agents = sum(len(s.get('agents', [])) for s in steps)
   suggested = total_agents * 3
   print(f'total_agent_calls_no_retry={total_agents} suggested_max_total_invocations={suggested}')
   " 2>/dev/null || true
   ```

   `total_agents` is every agent call across every step's chain if nothing
   ever needs a retry (the best case). The `× 3` is a heuristic cushion —
   room for roughly two extra full retries spread across the whole plan
   (the real per-step retry ceiling is `--max-step-exec-iterations`,
   default 5, so a single very stubborn step could still exceed this
   suggestion; it is a sane starting point, not a guarantee). Present it as
   a suggestion the user can accept or override, never silently substitute
   it as a hidden default.

   **Important caveat to relay to the user**: `--max-total-invocations`
   only counts **agent-execution** calls (the `Agent(...)` chain
   `orchestrator.py` runs per step) — it does **not** count codex-review or
   fix-cycle subprocess calls (`--max-step-review-iterations`, default 3
   rounds per step). A step stuck oscillating through review/fix rounds
   consumes real wall-clock time without ever touching the invocation
   counter. So `--max-total-invocations` alone does not bound how long a
   run can take — only `--max-wall-clock-s` does (it's checked on elapsed
   time directly, independent of what's consuming it). For a plan expected
   to legitimately run long (many steps, or steps likely to need a few
   review rounds), the right move is not to avoid a wall-clock budget — it
   is to pair the suggested invocation count with a **generously-sized**
   `--max-wall-clock-s` (e.g. a few hours), so neither a runaway retry
   storm nor a runaway review oscillation goes unbounded. The two flags are
   not mutually exclusive; giving both is normal and often the right call.

6. **Report back.** Reply with: the resolved JSON path, step count,
   `lang`/`py_sub`, the previewed slug, the suggested
   `--max-total-invocations` (with the caveat above), and the exact
   ready-to-paste follow-up command with the JSON path and the suggested
   invocation count already filled in:

   ```
   /mempaw-loop-start --project-root <fill in> --plan-json <out-path> --base <fill in> --max-total-invocations <suggested> --max-wall-clock-s <fill in — size generously if this plan may run long>
   ```

   This command does not know the target `--project-root` / `--base`, and
   cannot responsibly guess a wall-clock ceiling (that depends on how long
   the user is willing to let it run) — those stay placeholders. It does
   not invoke `/mempaw-loop-start` itself; the two stay separately
   composable.

## Arguments

$ARGUMENTS:
- `--md <path>` optional — an existing `/plan-orchestrate` markdown output.
  Defaults to the most recent such output already in this conversation.
- `--out <path>` optional — where to write the parsed JSON. Defaults to the
  source path with its extension swapped to `.json`.
