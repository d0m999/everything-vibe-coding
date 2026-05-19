"""Unit tests for :class:`orchestrator.ProcessRunner` subprocess handling (plan §5.1 #11).

Coverage targets the three subprocess outcome states the runner has to handle:

- ``exit=0``           — subprocess.run returns a clean CompletedProcess
- ``exit≠0``           — subprocess.run returns a non-zero CompletedProcess
- ``TimeoutExpired``   — subprocess.run raises TimeoutExpired; the runner
                         re-raises (the caller — :class:`StepRunner` — is the
                         layer that translates this into ``status='crashed'``;
                         see ``test_orchestrator_skeleton.py`` for that path)

The argv shape and the stdout/stderr file-output paths are covered by
``test_orchestrator_skeleton.py``; these tests stay narrowly focused on the
subprocess return / raise contract.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import orchestrator
from orchestrator import ProcessResult, ProcessRunner


def _mk_completed(
    argv: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a realistic CompletedProcess (all four fields populated)."""
    return subprocess.CompletedProcess(
        args=argv,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _patch_run(monkeypatch: pytest.MonkeyPatch, side_effect: Any) -> MagicMock:
    """Replace ``subprocess.run`` *inside ``orchestrator``* with a spy."""
    spy = MagicMock(side_effect=side_effect)
    monkeypatch.setattr(orchestrator.subprocess, "run", spy)
    return spy


def test_exit_zero_returns_returncode_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """subprocess exits 0 → ProcessResult.returncode == 0, stderr_nonempty=False."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return _mk_completed(argv, returncode=0, stdout='{"hello":"world"}\n', stderr="")

    _patch_run(monkeypatch, fake)
    runner = ProcessRunner()

    result = runner.run(
        prompt="echo",
        work_dir=tmp_path,
        agent_name="tdd-guide",
        agent_index=1,
    )

    assert isinstance(result, ProcessResult)
    assert result.returncode == 0
    assert result.stderr_nonempty is False
    # stdout was written to the .jsonl file (verified more thoroughly in
    # test_orchestrator_skeleton.py; here we just confirm the file exists)
    assert result.stdout_path.exists()
    assert result.stdout_path.read_text(encoding="utf-8") == '{"hello":"world"}\n'


def test_exit_nonzero_returns_returncode_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """subprocess exits 1 → ProcessResult.returncode == 1, stderr captured."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return _mk_completed(argv, returncode=1, stdout="", stderr="auth error")

    _patch_run(monkeypatch, fake)
    runner = ProcessRunner()

    result = runner.run(
        prompt="echo",
        work_dir=tmp_path,
        agent_name="python-reviewer",
        agent_index=2,
    )

    assert result.returncode == 1
    assert result.stderr_nonempty is True
    assert result.stderr_path.read_text(encoding="utf-8") == "auth error"


def test_timeout_expired_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """subprocess.run raises TimeoutExpired → ProcessRunner.run() re-raises it.

    The StepRunner layer catches this and marks the step ``crashed``
    (plan §5.4 B4 — not fail-fast); see ``test_orchestrator_skeleton.py``
    for the StepRunner side of this contract.
    """

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        # Genuine raise — not a fake return code masquerading as a timeout.
        raise subprocess.TimeoutExpired(cmd=argv, timeout=600)

    _patch_run(monkeypatch, fake)
    runner = ProcessRunner()

    with pytest.raises(subprocess.TimeoutExpired) as excinfo:
        runner.run(
            prompt="hangs forever",
            work_dir=tmp_path,
            agent_name="tdd-guide",
            agent_index=1,
        )

    # Confirm the exception carries the original timeout value through.
    assert excinfo.value.timeout == 600


def test_shell_false_and_text_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ProcessRunner must NOT use shell=True; argv must be a list (no string-cmd).

    This guards the plan §5.4 invariant against accidental regression to
    ``shell=True`` (which would re-introduce a shell-metachar injection vector
    via prompt content).
    """

    captured: dict[str, Any] = {}

    def fake(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv_type"] = type(argv)
        captured["argv_first"] = argv[0] if argv else None
        captured["kwargs"] = kwargs
        return _mk_completed(argv, returncode=0)

    _patch_run(monkeypatch, fake)
    ProcessRunner().run(
        prompt="prompt with ; metachars && rm -rf /",
        work_dir=tmp_path,
        agent_name="tdd-guide",
        agent_index=1,
    )

    assert captured["argv_type"] is list
    assert captured["argv_first"] == "claude"
    assert captured["kwargs"].get("shell", False) is False
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["capture_output"] is True
