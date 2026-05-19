"""Unit tests for ``quality_gate.run_quality_gate`` (plan §5.1 #10).

Coverage targets (plan §5.4 short-circuit, review B3/B4):

- all_passed: ruff returncode=0 → pytest returncode=0  → ``status=passed``
- ruff_failed: ruff returncode=1                       → ``status=quality_gate_failed``,
  pytest is **not** invoked (short-circuit assertion)
- pytest_failed: ruff returncode=0 → pytest returncode=1
                                                       → ``status=quality_gate_failed``
- tooling_missing (ruff): subprocess.run raises ``FileNotFoundError`` on ruff
                                                       → ``status=tooling_missing``
- tooling_missing (pytest): ruff returncode=0 → subprocess.run raises
  ``FileNotFoundError`` on pytest                      → ``status=tooling_missing``
- cwd argument is threaded through to ``subprocess.run``

All tests stub ``subprocess.run`` via ``monkeypatch`` — no real ruff / pytest
binary is invoked, so the tests run on any machine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import quality_gate
from quality_gate import GateStatus, run_quality_gate


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


def _install_fake_run(monkeypatch: pytest.MonkeyPatch, fake: Any) -> MagicMock:
    """Replace ``subprocess.run`` *inside ``quality_gate``* with a spy.

    We patch the binding the module already imported (``quality_gate.subprocess.run``)
    rather than ``subprocess.run`` globally so unrelated subprocesses in
    other tests are not affected.
    """
    spy = MagicMock(side_effect=fake)
    monkeypatch.setattr(quality_gate.subprocess, "run", spy)
    return spy


def test_all_passed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both ruff and pytest exit 0 → status='passed' and both per-cmd dicts present."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return _mk_completed(argv, returncode=0, stdout="ok", stderr="")

    spy = _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.PASSED.value
    assert result["ruff"] is not None
    assert result["pytest"] is not None
    assert result["ruff"]["returncode"] == 0
    assert result["pytest"]["returncode"] == 0
    assert spy.call_count == 2
    # Both invocations got cwd= explicitly (no shell cd && cmd).
    for call in spy.call_args_list:
        assert call.kwargs["cwd"] == tmp_path
        assert call.kwargs.get("shell", False) is False


def test_ruff_failed_short_circuits_pytest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-zero ruff exit → quality_gate_failed, pytest is NOT invoked."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        # ruff is the only call we should ever see.
        assert argv[0] == "ruff", f"unexpected subprocess after ruff failure: {argv}"
        return _mk_completed(argv, returncode=1, stdout="", stderr="E501 too long")

    spy = _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.QUALITY_GATE_FAILED.value
    assert result["ruff"] is not None
    assert result["ruff"]["returncode"] == 1
    assert "E501" in result["ruff"]["stderr_tail"]
    assert result["pytest"] is None, "pytest must not run when ruff fails (short-circuit)"
    assert spy.call_count == 1  # short-circuit assertion


def test_pytest_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ruff passes, pytest exits 1 → quality_gate_failed; both per-cmd dicts present."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "ruff":
            return _mk_completed(argv, returncode=0)
        if argv[0] == "pytest":
            return _mk_completed(argv, returncode=1, stdout="", stderr="1 failed")
        raise AssertionError(f"unexpected argv: {argv}")

    spy = _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.QUALITY_GATE_FAILED.value
    assert result["ruff"] is not None and result["ruff"]["returncode"] == 0
    assert result["pytest"] is not None and result["pytest"]["returncode"] == 1
    assert "1 failed" in result["pytest"]["stderr_tail"]
    assert spy.call_count == 2


def test_tooling_missing_ruff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ruff binary not on PATH → FileNotFoundError → status='tooling_missing'."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory: 'ruff'")

    spy = _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.TOOLING_MISSING.value
    assert result["ruff"] is None
    assert result["pytest"] is None
    assert spy.call_count == 1  # never tried pytest


def test_tooling_missing_pytest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ruff present + clean, pytest binary missing → status='tooling_missing'."""

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "ruff":
            return _mk_completed(argv, returncode=0)
        raise FileNotFoundError(2, "No such file or directory: 'pytest'")

    spy = _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.TOOLING_MISSING.value
    assert result["ruff"] is not None and result["ruff"]["returncode"] == 0
    assert result["pytest"] is None
    assert spy.call_count == 2


def test_cwd_passed_to_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """tools_dir argument must be passed as ``cwd=`` to every subprocess call.

    Plan §5.4 / review: no ``shell=True``, no ``cd && cmd`` — every binary
    runs with ``cwd=tools_dir`` so the working directory cannot be smuggled
    through shell metacharacters.
    """

    def fake(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return _mk_completed(argv, returncode=0)

    spy = _install_fake_run(monkeypatch, fake)
    run_quality_gate(tmp_path)

    for call in spy.call_args_list:
        assert call.kwargs["cwd"] == tmp_path
        # Defense in depth: ensure no shell, no extra positional args.
        assert call.kwargs.get("shell", False) is False
        assert call.kwargs.get("text") is True
        assert call.kwargs.get("capture_output") is True


def test_ruff_timeout_marks_quality_gate_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ruff hangs → TimeoutExpired → quality_gate_failed (does NOT crash gate).

    Gate failure must never raise into the orchestrator (plan §5.4 B4).  The
    timeout is encoded as a synthetic returncode=124 in the per-cmd dict and
    surfaced via the stderr_tail so operators can tell it apart from a real
    ruff lint failure.
    """

    def fake(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 120))

    _install_fake_run(monkeypatch, fake)
    result = run_quality_gate(tmp_path)

    assert result["status"] == GateStatus.QUALITY_GATE_FAILED.value
    assert result["ruff"] is not None
    assert result["ruff"]["returncode"] == 124  # synthetic timeout exit
    assert "timed out" in result["ruff"]["stderr_tail"]
    assert result["pytest"] is None  # short-circuit applies to timeout too


def test_status_values_match_gatestatus_enum() -> None:
    """The returned status must come from :class:`GateStatus` (no string drift)."""
    assert GateStatus.PASSED.value == "passed"
    assert GateStatus.QUALITY_GATE_FAILED.value == "quality_gate_failed"
    assert GateStatus.TOOLING_MISSING.value == "tooling_missing"
