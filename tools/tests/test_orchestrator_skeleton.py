"""TDD tests for orchestrator.py process-orchestration skeleton (step-7).

Test scope
----------
- test_process_runner_argv_shape
    Verifies the exact CLI argv passed to claude -p: no Task in --allowedTools,
    --max-turns 40, --session-id is a UUID4 string, no shell=True.

- test_process_runner_writes_stdout_and_stderr_to_separate_files
    Mocks subprocess returning stdout + non-empty stderr; asserts .jsonl gets
    stdout and .stderr.log gets stderr.

- test_step_runner_uses_hello_world_fixture
    Builds a minimal PlanResult-shaped dict (1 step / 1 agent), mocks
    subprocess.run to rc=0, runs StepRunner, asserts correct disk layout and
    step status == 'passed' (QualityGate mocked to 'passed').

- test_step_runner_marks_crash_on_nonzero_exit
    Mocks subprocess rc=2; asserts step.status == 'crashed' AND the function
    returns instead of raising (outer loop continues).

Out of scope for this step
--------------------------
- Real claude -p invocation (Checkpoint B, step-8)
- HANDOFF splice between agents (step-9)
- Full QualityGate unit tests (step-10b)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from orchestrator import GateResult, ProcessRunner, QualityGate, StepRunner, run_plan
from plan_md_to_json import AgentEntry, StepEntry

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_agent(name: str = "tdd-guide", prompt: str = "Hello world prompt.") -> AgentEntry:
    return AgentEntry(name=name, prompt=prompt)


def _make_step(
    step_id: int = 1,
    title: str = "Test Step",
    agents: list[AgentEntry] | None = None,
) -> StepEntry:
    if agents is None:
        agents = [_make_agent()]
    return StepEntry(
        id=step_id,
        title=title,
        tags=["impl"],
        chain="tdd-guide",
        agents=agents,
    )


def _fake_completed_process(
    returncode: int = 0,
    stdout: str = '{"type":"result"}\n',
    stderr: str = "",
) -> MagicMock:
    """Return a mock that mimics subprocess.CompletedProcess."""
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


# ---------------------------------------------------------------------------
# ProcessRunner tests
# ---------------------------------------------------------------------------


class TestProcessRunnerArgvShape:
    """test_process_runner_argv_shape: assert the subprocess argv matches §5.3."""

    def test_argv_starts_with_claude_p(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert argv[0] == "claude"
        assert argv[1] == "-p"
        assert argv[2] == "hello"

    def test_argv_contains_allowed_tools_flag(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert "--allowedTools" in argv
        idx = argv.index("--allowedTools")
        tools_value = argv[idx + 1]
        assert "Task" not in tools_value, (
            f"--allowedTools must NOT contain 'Task' — got: {tools_value!r}"
        )
        # Must contain the required tools
        for required in ("Read", "Edit", "Write", "Bash"):
            assert required in tools_value, f"Expected {required!r} in --allowedTools"

    def test_argv_max_turns_is_40(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert "--max-turns" in argv
        idx = argv.index("--max-turns")
        assert argv[idx + 1] == "40"

    def test_argv_session_id_is_uuid4(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert "--session-id" in argv
        idx = argv.index("--session-id")
        session_id_str = argv[idx + 1]
        # Must be a valid UUID
        parsed = uuid.UUID(session_id_str)
        assert parsed.version == 4, f"Expected UUID v4, got version={parsed.version}"

    def test_argv_no_shell_true(self, tmp_path: Path) -> None:
        """subprocess.run must be called with shell=False (or shell not set at all)."""
        runner = ProcessRunner()
        kwargs_captured: list[dict[str, Any]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            kwargs_captured.append(kwargs)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        kw = kwargs_captured[0]
        assert kw.get("shell", False) is False, (
            "subprocess.run must NOT use shell=True"
        )

    def test_argv_output_format_stream_json(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert "--output-format" in argv
        idx = argv.index("--output-format")
        assert argv[idx + 1] == "stream-json"

    def test_argv_contains_print_flag(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        captured: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            captured.append(argv)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        argv = captured[0]
        assert "--print" in argv

    def test_argv_text_true_and_capture_output(self, tmp_path: Path) -> None:
        """subprocess.run must use text=True and capture_output=True."""
        runner = ProcessRunner()
        kwargs_captured: list[dict[str, Any]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            kwargs_captured.append(kwargs)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        kw = kwargs_captured[0]
        assert kw.get("text") is True
        assert kw.get("capture_output") is True

    def test_argv_timeout_is_600(self, tmp_path: Path) -> None:
        """subprocess.run must be called with timeout=600."""
        runner = ProcessRunner()
        kwargs_captured: list[dict[str, Any]] = []

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            kwargs_captured.append(kwargs)
            return _fake_completed_process()

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            runner.run(prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1)

        kw = kwargs_captured[0]
        assert kw.get("timeout") == 600


# ---------------------------------------------------------------------------
# ProcessRunner stdout/stderr file output tests
# ---------------------------------------------------------------------------


class TestProcessRunnerFileOutput:
    """test_process_runner_writes_stdout_and_stderr_to_separate_files."""

    def test_stdout_written_to_jsonl_file(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        stdout_content = '{"type":"result","data":"ok"}\n'

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(stdout=stdout_content, stderr=""),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert result.stdout_path.exists()
        assert result.stdout_path.suffix == ".jsonl"
        assert result.stdout_path.read_text(encoding="utf-8") == stdout_content

    def test_stderr_written_to_stderr_log_file(self, tmp_path: Path) -> None:
        runner = ProcessRunner()
        stderr_content = "Warning: something happened\n"

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(stdout='{"ok":true}\n', stderr=stderr_content),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert result.stderr_path.exists()
        assert result.stderr_path.name.endswith(".stderr.log")
        assert result.stderr_path.read_text(encoding="utf-8") == stderr_content

    def test_stderr_nonempty_flag_true_when_stderr_present(self, tmp_path: Path) -> None:
        runner = ProcessRunner()

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(stderr="Error: auth failed\n"),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert result.stderr_nonempty is True

    def test_stderr_nonempty_flag_false_when_stderr_empty(self, tmp_path: Path) -> None:
        runner = ProcessRunner()

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(stderr=""),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert result.stderr_nonempty is False

    def test_result_has_returncode(self, tmp_path: Path) -> None:
        runner = ProcessRunner()

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=0),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert result.returncode == 0

    def test_result_has_duration_s_float(self, tmp_path: Path) -> None:
        runner = ProcessRunner()

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="tdd-guide", agent_index=1
            )

        assert isinstance(result.duration_s, float)
        assert result.duration_s >= 0.0

    def test_file_names_include_agent_index_and_name(self, tmp_path: Path) -> None:
        runner = ProcessRunner()

        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            result = runner.run(
                prompt="hello", work_dir=tmp_path, agent_name="python-reviewer", agent_index=3
            )

        assert "3" in result.stdout_path.name
        assert "python-reviewer" in result.stdout_path.name
        assert "3" in result.stderr_path.name
        assert "python-reviewer" in result.stderr_path.name


# ---------------------------------------------------------------------------
# StepRunner: hello-world fixture (1 step, 1 agent, gate mocked to passed)
# ---------------------------------------------------------------------------


class TestStepRunnerHelloWorldFixture:
    """test_step_runner_uses_hello_world_fixture: disk layout + status=passed."""

    def test_step_dir_created_under_work_dir(self, tmp_path: Path) -> None:
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(
            status="passed", stdout="", stderr=""
        )

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            runner.run_step(step)

        # A step-1/ directory must exist inside the work_dir
        step_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and "step-1" in d.name]
        assert len(step_dirs) == 1, f"Expected a step-1 dir under {tmp_path}"

    def test_agent_jsonl_file_exists(self, tmp_path: Path) -> None:
        step = _make_step(agents=[_make_agent(name="tdd-guide")])

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            runner.run_step(step)

        # Find any .jsonl file anywhere under tmp_path
        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) >= 1, "Expected at least one .jsonl file"
        assert any("tdd-guide" in f.name for f in jsonl_files)

    def test_agent_stderr_log_file_exists(self, tmp_path: Path) -> None:
        step = _make_step(agents=[_make_agent(name="tdd-guide")])

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            runner.run_step(step)

        stderr_files = list(tmp_path.rglob("*.stderr.log"))
        assert len(stderr_files) >= 1, "Expected at least one .stderr.log file"

    def test_step_status_passed_when_gate_passes(self, tmp_path: Path) -> None:
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="All good", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=0),
        ):
            status = runner.run_step(step).status

        assert status == "passed"

    def test_two_agents_produce_two_jsonl_files(self, tmp_path: Path) -> None:
        step = _make_step(
            agents=[
                _make_agent(name="tdd-guide"),
                _make_agent(name="python-reviewer"),
            ]
        )

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(),
        ):
            runner.run_step(step)

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) == 2, f"Expected 2 .jsonl files, got {len(jsonl_files)}"


# ---------------------------------------------------------------------------
# StepRunner: crash on non-zero subprocess exit
# ---------------------------------------------------------------------------


class TestStepRunnerCrashHandling:
    """test_step_runner_marks_crash_on_nonzero_exit."""

    def test_status_is_crashed_when_subprocess_returns_nonzero(self, tmp_path: Path) -> None:
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=2),
        ):
            status = runner.run_step(step).status

        assert status == "crashed"

    def test_run_step_does_not_raise_on_crash(self, tmp_path: Path) -> None:
        """run_step() must return (not raise) so the outer loop can continue."""
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=1),
        ):
            try:
                status = runner.run_step(step).status
            except Exception as exc:
                pytest.fail(f"run_step() raised unexpectedly: {exc!r}")

        assert status == "crashed"

    def test_status_is_crashed_when_subprocess_times_out(self, tmp_path: Path) -> None:
        """subprocess.TimeoutExpired must be caught and return 'crashed'."""
        import subprocess

        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=600),
        ):
            status = runner.run_step(step).status

        assert status == "crashed"

    def test_quality_gate_not_called_when_subprocess_crashes(self, tmp_path: Path) -> None:
        """If any subprocess call in a step crashes, the quality gate should be skipped."""
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=2),
        ):
            runner.run_step(step)

        mock_gate.run.assert_not_called()


# ---------------------------------------------------------------------------
# StepRunner: quality gate failure
# ---------------------------------------------------------------------------


class TestStepRunnerQualityGateFailure:
    """StepRunner returns 'quality_gate_failed' when QualityGate.run() returns that status."""

    def test_status_quality_gate_failed_when_gate_fails(self, tmp_path: Path) -> None:
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(
            status="quality_gate_failed", stdout="", stderr="ruff: E501 line too long"
        )

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=0),
        ):
            status = runner.run_step(step).status

        assert status == "quality_gate_failed"

    def test_run_step_does_not_raise_on_gate_failure(self, tmp_path: Path) -> None:
        """Gate failure must not raise; outer loop continues."""
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(
            status="quality_gate_failed", stdout="", stderr="pytest: 1 failed"
        )

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=0),
        ):
            try:
                status = runner.run_step(step).status
            except Exception as exc:
                pytest.fail(f"run_step() raised unexpectedly on gate failure: {exc!r}")

        assert status == "quality_gate_failed"


# ---------------------------------------------------------------------------
# stderr surface (plan §5.4 A2) — review F1 fix
# ---------------------------------------------------------------------------


class TestStderrSurfaceInStepResult:
    """run_step() must propagate stderr_warnings via _StepResult (review F1)."""

    def test_nonempty_stderr_populates_warnings(self, tmp_path: Path) -> None:
        step = _make_step(
            agents=[
                _make_agent(name="tdd-guide"),
                _make_agent(name="python-reviewer"),
            ]
        )

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        # Agent 1 produces stderr, agent 2 is clean.
        responses = [
            _fake_completed_process(returncode=0, stderr="rate limit hit\n"),
            _fake_completed_process(returncode=0, stderr=""),
        ]
        with patch("orchestrator.subprocess.run", side_effect=responses):
            result = runner.run_step(step)

        assert result.status == "passed"
        assert len(result.stderr_warnings) == 1
        assert "agent-1-tdd-guide" in result.stderr_warnings[0]

    def test_crash_path_records_warning(self, tmp_path: Path) -> None:
        step = _make_step()

        mock_gate = MagicMock(spec=QualityGate)
        mock_gate.run.return_value = GateResult(status="passed", stdout="", stderr="")

        runner = StepRunner(work_dir=tmp_path, quality_gate=mock_gate)
        with patch(
            "orchestrator.subprocess.run",
            return_value=_fake_completed_process(returncode=2, stderr="boom\n"),
        ):
            result = runner.run_step(step)

        assert result.status == "crashed"
        # Non-empty stderr warning is recorded even on crash
        assert any("agent-1-tdd-guide" in w for w in result.stderr_warnings)


# ---------------------------------------------------------------------------
# run_plan integration (plan §5.4 B4 + §6) — review F4
# ---------------------------------------------------------------------------


def _write_plan_json(path: Path, n_steps: int = 2) -> None:
    """Write a minimal plan.orchestrate.json with N single-agent steps."""
    plan = {
        "meta": {
            "plan": "fixture",
            "lang": "python",
            "py_sub": "generic",
            "steps_count": n_steps,
            "scope": "all",
        },
        "steps": [
            {
                "id": i + 1,
                "title": f"step-{i + 1}",
                "tags": ["impl"],
                "chain": "tdd-guide",
                "agents": [{"name": "tdd-guide", "prompt": f"prompt-{i + 1}"}],
            }
            for i in range(n_steps)
        ],
        "parallel_graph": {"waves": [], "deps": []},
    }
    path.write_text(json.dumps(plan), encoding="utf-8")


class TestRunPlanIntegration:
    """run_plan() must continue past crashes and surface stderr in summary."""

    def test_two_consecutive_crashes_both_execute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plan §5.4 B4: crashed steps must NOT fail-fast.

        Both steps run, both end up in summary.json, exit code is 2 (crashed
        outranks quality_gate_failed per §6 precedence).
        """
        plan_path = tmp_path / "plan.orchestrate.json"
        _write_plan_json(plan_path, n_steps=2)

        # Run from inside tmp_path so .work/run-... lands there, not in repo.
        monkeypatch.chdir(tmp_path)

        call_count = {"n": 0}

        def fake_run(argv: list[str], **kwargs: Any) -> MagicMock:
            call_count["n"] += 1
            return _fake_completed_process(returncode=2, stderr="kaboom\n")

        with patch("orchestrator.subprocess.run", side_effect=fake_run):
            exit_code = run_plan(plan_path)

        # Both steps' subprocesses executed (1 agent each = 2 total)
        assert call_count["n"] == 2
        assert exit_code == 2  # crashed > quality_gate_failed per §6

        # summary.json exists and lists both steps as crashed
        runs = list((tmp_path / ".work").glob("run-*"))
        assert len(runs) == 1
        summary = json.loads((runs[0] / "summary.json").read_text(encoding="utf-8"))
        assert [s["status"] for s in summary["steps"]] == ["crashed", "crashed"]

    def test_summary_contains_stderr_warnings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plan §5.4 A2: non-empty stderr must surface in summary.json."""
        plan_path = tmp_path / "plan.orchestrate.json"
        _write_plan_json(plan_path, n_steps=1)
        monkeypatch.chdir(tmp_path)

        # Subprocess succeeds but emits stderr; quality gate passes via patch.
        with (
            patch(
                "orchestrator.subprocess.run",
                return_value=_fake_completed_process(returncode=0, stderr="warn\n"),
            ),
            patch.object(
                QualityGate,
                "run",
                return_value=GateResult(status="passed", stdout="", stderr=""),
            ),
        ):
            exit_code = run_plan(plan_path)

        assert exit_code == 0
        runs = list((tmp_path / ".work").glob("run-*"))
        summary = json.loads((runs[0] / "summary.json").read_text(encoding="utf-8"))
        assert len(summary["steps"]) == 1
        warnings = summary["steps"][0]["stderr_warnings"]
        assert len(warnings) == 1
        assert "non-empty stderr" in warnings[0]
