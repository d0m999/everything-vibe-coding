"""Orchestrator harness — process orchestration skeleton (step-7).

Architecture
------------
Four classes handle separate responsibilities (plan §5.1 #4, review B2):

ProcessRunner
    Wraps a single ``subprocess.run`` invocation of ``claude -p``.
    Writes stdout to ``<work_dir>/agent-{K}-{name}.jsonl`` and
    stderr to ``<work_dir>/agent-{K}-{name}.stderr.log``.

HandoffExtractor (thin wrapper)
    Delegates to ``handoff_extractor.extract_handoff()``.
    Scans stream-json JSONL for the last ``<handoff>...</handoff>`` block across
    all assistant turns; falls back to ``MISSING_HANDOFF_PLACEHOLDER``.

QualityGate
    Runs ``cd tools && ruff check . && pytest -x`` and returns a GateResult.

StepRunner
    Orchestrates one StepEntry: creates the work directory, iterates agents
    sequentially via ProcessRunner, runs QualityGate, returns status string.

CLI entry
---------
``python orchestrator.py <plan.orchestrate.json>``
    Reads the pre-parsed JSON file (use plan_md_to_json.parse_file() on the
    markdown source first), runs each step in order, writes
    ``.work/run-{ISO}/summary.json``, and prints a console summary table.

Exit codes (plan §6)
--------------------
0 — all steps passed quality gate
1 — one or more steps are ``quality_gate_failed``
2 — one or more steps are ``crashed``

Technical decisions encoded here (plan §5.4)
--------------------------------------------
- subprocess.run (sync, not asyncio — MVP is sequential)
- --session-id: uuid.uuid4() per call, logging tag only (headless has no
  persisted state)
- --allowedTools: "Read,Edit,Write,Bash,Grep,Glob" — NO "Task" so that
  Python (not the subprocess) owns the chain; subprocesses must not spawn
  further subagents
- --max-turns=40 (hard-coded; v2 candidate: per-agent-type levels)
- stderr written to separate .stderr.log; non-empty surfaced in summary
- Step crash: mark crashed, continue (not fail-fast); aligns with
  quality_gate_failed behaviour (plan §5.4 B4)
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from handoff_extractor import extract_handoff
from plan_md_to_json import StepEntry
from quality_gate import GateStatus, run_quality_gate

# ---------------------------------------------------------------------------
# Constants (plan §5.4)
# ---------------------------------------------------------------------------
_ALLOWED_TOOLS = "Read,Edit,Write,Bash,Grep,Glob"
# IMPORTANT: "Task" is intentionally excluded — Python owns the chain.
# Subprocesses must not spawn further subagents.

_MAX_TURNS = "40"
# v2 candidate: per-agent-type levels (reviewer=20, impl=60) — plan §5.4 B5

_SUBPROCESS_TIMEOUT = 600  # seconds — may be too short for impl-class agents
# Risk: long-running agents may exceed 600 s.  v2 candidate: configurable.

_TOOLS_DIR = Path(__file__).parent  # tools/ directory


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessResult:
    """Result of a single claude -p subprocess invocation."""

    returncode: int
    stdout_path: Path
    stderr_path: Path
    prompt_path: Path
    stderr_nonempty: bool
    duration_s: float


@dataclass(frozen=True)
class GateResult:
    """Result of a quality gate run."""

    status: Literal["passed", "quality_gate_failed", "tooling_missing"]
    stdout: str
    stderr: str


# ---------------------------------------------------------------------------
# ProcessRunner
# ---------------------------------------------------------------------------

class ProcessRunner:
    """Wraps a single ``subprocess.run`` invocation of ``claude -p``.

    The subprocess argv shape (plan §5.3 step 7)::

        ['claude', '-p', '<prompt>',
         '--allowedTools', 'Read,Edit,Write,Bash,Grep,Glob',
         '--max-turns', '40',
         '--session-id', '<uuid4>',
         '--output-format', 'stream-json',
         '--verbose']

    Note: ``-p`` enables print/non-interactive mode; ``--verbose`` is required
    by the CLI when combining ``-p`` with ``--output-format=stream-json``.

    Keyword args to subprocess.run:
        text=True, capture_output=True, timeout=600, shell=False (default).
    """

    def run(
        self,
        *,
        prompt: str,
        work_dir: Path,
        agent_name: str,
        agent_index: int,
    ) -> ProcessResult:
        """Invoke ``claude -p`` and write stdout/stderr to separate files.

        Parameters
        ----------
        prompt:
            The full prompt string to pass as the positional argument to
            ``claude -p``.
        work_dir:
            Directory under which to write ``agent-{agent_index}-{agent_name}.jsonl``
            and ``agent-{agent_index}-{agent_name}.stderr.log``.
        agent_name:
            Name label used in output filenames (e.g. ``"tdd-guide"``).
        agent_index:
            1-based index of this agent within its step chain.

        Returns
        -------
        ProcessResult
            Frozen dataclass with returncode, paths to stdout/stderr files,
            a flag for whether stderr is non-empty, and wall-clock duration.
        """
        session_id = str(uuid.uuid4())
        # session-id: per-call UUID v4, logging tag only.
        # headless claude -p has no persisted state; session-id is not reused.

        argv = [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            _ALLOWED_TOOLS,
            "--max-turns",
            _MAX_TURNS,
            "--session-id",
            session_id,
            "--output-format",
            "stream-json",
            "--verbose",
            # NOTE: --verbose is required when combining --print with
            # --output-format=stream-json (claude CLI enforces this).
        ]

        stdout_path = work_dir / f"agent-{agent_index}-{agent_name}.jsonl"
        stderr_path = work_dir / f"agent-{agent_index}-{agent_name}.stderr.log"
        prompt_path = work_dir / f"agent-{agent_index}-{agent_name}.prompt.txt"

        work_dir.mkdir(parents=True, exist_ok=True)

        # Audit trail: write the full prompt (including any HANDOFF splice) to
        # disk BEFORE invoking the subprocess.  This makes post-hoc inspection
        # possible via plain `cat` without parsing stream-json. (plan §5.4)
        prompt_path.write_text(prompt, encoding="utf-8")

        t_start = _monotonic()
        completed = subprocess.run(  # noqa: S603  (shell=False by default — no injection risk)
            argv,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        duration_s = _monotonic() - t_start

        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        return ProcessResult(
            returncode=completed.returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            prompt_path=prompt_path,
            stderr_nonempty=bool(completed.stderr),
            duration_s=duration_s,
        )


def _monotonic() -> float:
    """Return a monotonic time value in seconds (wall-clock proxy for tests)."""
    import time
    return time.monotonic()


# ---------------------------------------------------------------------------
# HandoffExtractor (thin wrapper around the stub module)
# ---------------------------------------------------------------------------

class HandoffExtractor:
    """Thin wrapper around handoff_extractor.extract_handoff().

    Keeping a class here means StepRunner can dependency-inject it for tests,
    and step-9 can swap the implementation without touching StepRunner.
    """

    def extract(self, jsonl_text: str) -> str:
        """Return the last HANDOFF JSON string or MISSING_HANDOFF_PLACEHOLDER."""
        return extract_handoff(jsonl_text)


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------

class QualityGate:
    """Thin quality gate: delegates to :func:`quality_gate.run_quality_gate`.

    Design decisions (plan §5.4, §7.1):
    - Uses ``subprocess.run`` with ``cwd=tools_dir`` and ``shell=False``
      (no ``cd && cmd`` shell chaining — see ``quality_gate`` module).
    - Failure marks the step ``quality_gate_failed`` but does NOT stop pipeline.
    - ``tooling_missing`` is returned when ruff or pytest is not on PATH.
    - Short-circuit: if ruff fails, pytest is not run.

    Why a wrapper? :class:`StepRunner` was originally written against this
    class so it could dependency-inject a mock; keeping the class preserves
    that seam (and the existing skeleton tests) while the actual work moved
    to a pure function that is easier to unit test.
    """

    def run(self) -> GateResult:
        """Execute the quality gate and return a :class:`GateResult`.

        The per-stage tails returned by
        :func:`quality_gate.run_quality_gate` are merged into the legacy
        ``stdout`` / ``stderr`` strings on :class:`GateResult` so callers
        that already format these into summaries keep working.
        """
        result = run_quality_gate(_TOOLS_DIR)

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        for stage in ("ruff", "pytest"):
            cmd_result = result.get(stage)
            if cmd_result is None:
                continue
            if cmd_result["stdout_tail"]:
                stdout_parts.append(f"=== {stage} stdout ===\n{cmd_result['stdout_tail']}")
            if cmd_result["stderr_tail"]:
                stderr_parts.append(f"=== {stage} stderr ===\n{cmd_result['stderr_tail']}")

        status = result["status"]
        if status == GateStatus.TOOLING_MISSING.value and not stderr_parts:
            stderr_parts.append("ruff or pytest binary not found on PATH")

        return GateResult(
            status=status,  # type: ignore[arg-type]  # values match the Literal alphabet
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
        )


# ---------------------------------------------------------------------------
# StepResult (internal record, not exposed as public API)
# ---------------------------------------------------------------------------

@dataclass
class _StepResult:
    step_id: int
    title: str
    status: Literal["passed", "quality_gate_failed", "crashed"]
    agent_results: list[ProcessResult]
    gate_result: GateResult | None
    stderr_warnings: list[str]


# ---------------------------------------------------------------------------
# StepRunner
# ---------------------------------------------------------------------------

class StepRunner:
    """Orchestrates one StepEntry: run agents sequentially, then quality gate.

    Disk layout per step (plan §5.2)::

        <work_dir>/
          step-{N}/
            agent-1-<name>.jsonl
            agent-1-<name>.stderr.log
            agent-2-<name>.jsonl
            agent-2-<name>.stderr.log

    Crash / gate failure behaviour (plan §5.4 B4):
    - Subprocess non-zero exit or TimeoutExpired → status='crashed', no gate
    - Gate failure → status='quality_gate_failed'
    - Both continue to next step (not fail-fast)
    """

    def __init__(
        self,
        work_dir: Path,
        quality_gate: QualityGate | None = None,
        handoff_extractor: HandoffExtractor | None = None,
    ) -> None:
        self._work_dir = work_dir
        self._gate = quality_gate if quality_gate is not None else QualityGate()
        self._handoff_extractor = (
            handoff_extractor if handoff_extractor is not None else HandoffExtractor()
        )
        self._process_runner = ProcessRunner()

    def run_step(self, step: StepEntry) -> _StepResult:
        """Run all agents in a step sequentially and return a full result.

        Parameters
        ----------
        step:
            A StepEntry from the parsed plan JSON.

        Returns
        -------
        _StepResult
            Includes ``status`` ('passed' / 'quality_gate_failed' / 'crashed'),
            per-agent ``ProcessResult`` list, optional ``GateResult``, and a
            ``stderr_warnings`` list surfaced from any agent with non-empty
            stderr (plan §5.4 A2).
            Never raises — caller's outer loop always continues.
        """
        step_dir = self._work_dir / f"step-{step['id']}"
        step_dir.mkdir(parents=True, exist_ok=True)

        agent_results: list[ProcessResult] = []
        stderr_warnings: list[str] = []

        # Run agents sequentially
        for agent_index, agent in enumerate(step["agents"], start=1):
            prompt = agent["prompt"]

            # Splice prior HANDOFF for non-first agents (plan §5.4).
            if agent_index > 1 and agent_results:
                prior_jsonl = agent_results[-1].stdout_path.read_text(encoding="utf-8")
                prior_handoff = self._handoff_extractor.extract(prior_jsonl)
                prev_name = step["agents"][agent_index - 2]["name"]
                prompt = f"[Prior HANDOFF from {prev_name}: {prior_handoff}]\n\n{prompt}"

            try:
                proc_result = self._process_runner.run(
                    prompt=prompt,
                    work_dir=step_dir,
                    agent_name=agent["name"],
                    agent_index=agent_index,
                )
            except subprocess.TimeoutExpired:
                stderr_warnings.append(
                    f"agent-{agent_index}-{agent['name']}: subprocess timeout"
                )
                return _StepResult(
                    step_id=step["id"],
                    title=step["title"],
                    status="crashed",
                    agent_results=agent_results,
                    gate_result=None,
                    stderr_warnings=stderr_warnings,
                )
            except Exception as exc:  # noqa: BLE001  (broad catch: network, OS errors)
                stderr_warnings.append(
                    f"agent-{agent_index}-{agent['name']}: subprocess error: {exc!r}"
                )
                return _StepResult(
                    step_id=step["id"],
                    title=step["title"],
                    status="crashed",
                    agent_results=agent_results,
                    gate_result=None,
                    stderr_warnings=stderr_warnings,
                )

            agent_results.append(proc_result)

            if proc_result.stderr_nonempty:
                stderr_warnings.append(
                    f"agent-{agent_index}-{agent['name']}: non-empty stderr"
                )

            if proc_result.returncode != 0:
                # Crash: mark and stop this step (plan §5.4 B4 — not fail-fast)
                return _StepResult(
                    step_id=step["id"],
                    title=step["title"],
                    status="crashed",
                    agent_results=agent_results,
                    gate_result=None,
                    stderr_warnings=stderr_warnings,
                )

        # All agents finished with rc=0 — run quality gate
        gate_result = self._gate.run()

        # Normalize gate status into the StepResult status alphabet.
        # 'tooling_missing' is reported as quality_gate_failed for the outer
        # exit-code contract (§6), but surfaced via stderr_warnings so callers
        # can distinguish the cause without widening the StepResult enum.
        step_status: Literal["passed", "quality_gate_failed", "crashed"]
        if gate_result.status == "passed":
            step_status = "passed"
        else:
            step_status = "quality_gate_failed"
            if gate_result.status == "tooling_missing":
                stderr_warnings.append(
                    "quality gate: tooling_missing "
                    "(ruff or pytest binary not found in PATH)"
                )

        return _StepResult(
            step_id=step["id"],
            title=step["title"],
            status=step_status,
            agent_results=agent_results,
            gate_result=gate_result,
            stderr_warnings=stderr_warnings,
        )


# ---------------------------------------------------------------------------
# Orchestrator (outer loop + CLI)
# ---------------------------------------------------------------------------

def run_plan(plan_json_path: Path) -> int:
    """Read a plan JSON file, run all steps, write summary, return exit code.

    Parameters
    ----------
    plan_json_path:
        Path to a ``plan.orchestrate.json`` file produced by
        ``plan_md_to_json.parse_file()``.

    Returns
    -------
    int
        0 = all passed, 1 = quality_gate_failed, 2 = crashed (plan §6).
    """
    plan_data = json.loads(plan_json_path.read_text(encoding="utf-8"))

    iso_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: UP017
    # Resolve to absolute so summary.json is self-contained — consumers
    # (ralph.sh outer loop, human readers) shouldn't have to know cwd.
    run_dir = (Path(".work") / f"run-{iso_ts}").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    gate = QualityGate()
    step_runner = StepRunner(work_dir=run_dir, quality_gate=gate)

    step_statuses: list[dict] = []
    any_crashed = False
    any_gate_failed = False

    for step in plan_data.get("steps", []):
        step_entry = StepEntry(
            id=step["id"],
            title=step["title"],
            tags=step.get("tags", []),
            chain=step.get("chain", ""),
            agents=step.get("agents", []),
        )

        result = step_runner.run_step(step_entry)

        step_statuses.append(
            {
                "step_id": step["id"],
                "title": step["title"],
                "status": result.status,
                "stderr_warnings": list(result.stderr_warnings),
            }
        )

        if result.status == "crashed":
            any_crashed = True
        elif result.status == "quality_gate_failed":
            any_gate_failed = True

    # Write summary.json (plan §5.2)
    summary = {
        "run_dir": str(run_dir),
        "iso_timestamp": iso_ts,
        "steps": step_statuses,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary table
    _print_summary_table(step_statuses, summary_path)

    # Exit codes (plan §6)
    if any_crashed:
        return 2
    if any_gate_failed:
        return 1
    return 0


def _print_summary_table(step_statuses: list[dict], summary_path: Path) -> None:
    """Print a human-readable summary table to stdout."""
    print()
    print("Orchestrator run complete")
    print("-" * 50)
    print(f"{'Step':<8} {'Status':<22} Title")
    print("-" * 50)
    for s in step_statuses:
        status_icon = {
            "passed": "[OK]",
            "quality_gate_failed": "[GATE]",
            "crashed": "[CRASH]",
        }.get(s["status"], s["status"])
        print(f"{s['step_id']:<8} {status_icon:<22} {s['title']}")
    print("-" * 50)
    print(f"Summary written to: {summary_path}")

    # Surface non-empty stderr warnings (plan §5.4 A2)
    warned_steps = [s for s in step_statuses if s.get("stderr_warnings")]
    if warned_steps:
        print()
        print("Warnings:")
        for s in warned_steps:
            for w in s["stderr_warnings"]:
                print(f"  step-{s['step_id']}: {w}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI: python orchestrator.py <plan.orchestrate.json>"""
    if len(sys.argv) != 2:
        print(
            "Usage: python orchestrator.py <plan.orchestrate.json>\n"
            "\n"
            "  plan.orchestrate.json  Path to the JSON file produced by\n"
            "                         plan_md_to_json.parse_file()\n",
            file=sys.stderr,
        )
        sys.exit(2)

    plan_json_path = Path(sys.argv[1])
    if not plan_json_path.exists():
        print(f"Error: file not found: {plan_json_path}", file=sys.stderr)
        sys.exit(2)

    exit_code = run_plan(plan_json_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
