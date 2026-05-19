"""Thin quality gate: ``ruff check . && pytest -x`` inside ``tools/``.

Public API
----------
run_quality_gate(tools_dir: Path) -> QualityGateResult
    Run ``ruff check .`` then ``pytest -x`` in ``tools_dir`` via ``subprocess.run``
    with ``cwd=`` (no shell).  Returns a TypedDict with:

    - ``status``  — ``"passed"`` | ``"quality_gate_failed"`` | ``"tooling_missing"``
    - ``ruff``    — per-command result (``returncode`` + 2KB stdout/stderr tails),
                    or ``None`` when the ruff binary itself was not found
    - ``pytest``  — same shape; ``None`` when ruff failed (short-circuit) or
                    pytest itself was not found

Design (plan §5.4, §7.1; review notes)
--------------------------------------
- ``subprocess.run`` with ``cwd=tools_dir``, ``shell=False`` — no
  shell-injection vector; ``cd && cmd`` shell chaining is explicitly avoided.
- ``FileNotFoundError`` (binary missing) is caught explicitly per stage and
  collapses to ``status="tooling_missing"`` so the orchestrator can degrade
  gracefully without crashing.
- Short-circuit: if ``ruff`` exits non-zero, ``pytest`` is **not** run.  This
  mirrors the ``&&`` semantics of the original shell command and avoids
  reporting pytest failures that are caused by lint debris.
- Status alphabet is fixed by :class:`GateStatus` (string Enum) so callers
  cannot accidentally compare against a stale literal.
"""

from __future__ import annotations

import subprocess
from enum import StrEnum
from pathlib import Path
from typing import TypedDict


class GateStatus(StrEnum):
    """Status alphabet for :func:`run_quality_gate`.

    ``StrEnum`` (3.11+) keeps the wire format compatible with the legacy
    ``GateResult.status`` ``Literal`` in :mod:`orchestrator` while preventing
    string-literal drift inside this module.
    """

    PASSED = "passed"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    TOOLING_MISSING = "tooling_missing"


class CmdResult(TypedDict):
    """Result of a single quality-gate subprocess invocation."""

    returncode: int
    stdout_tail: str
    stderr_tail: str


class QualityGateResult(TypedDict):
    """Aggregate quality-gate outcome.

    ``ruff`` is ``None`` only when the ruff binary itself was not found
    (status will be ``tooling_missing``).  ``pytest`` is ``None`` when:

    - ruff was not found (we never got to pytest), or
    - ruff exited non-zero (short-circuit), or
    - the pytest binary itself was not found.

    Callers should branch on ``status``; the per-command dicts are for logs
    and debugging only.
    """

    status: str
    ruff: CmdResult | None
    pytest: CmdResult | None


# Defaults — kept module-level so tests can monkeypatch if needed.
_TAIL_CHARS = 2000
_TIMEOUT_S = 120


def _tail(s: str | None, n: int = _TAIL_CHARS) -> str:
    if not s:
        return ""
    return s[-n:]


def _run_stage(argv: list[str], cwd: Path) -> CmdResult | None:
    """Run one stage.

    Return values:

    - :class:`CmdResult` with the actual ``returncode`` and stdout/stderr tails
      when the stage ran to completion (zero or non-zero exit).
    - ``None`` when the binary itself was not found (graceful degradation —
      the caller maps this to ``status='tooling_missing'``).
    - :class:`CmdResult` with synthetic ``returncode=124`` and a stderr tail
      noting the timeout when the stage exceeds ``_TIMEOUT_S`` seconds.  Using
      a non-zero returncode keeps the gate's contract intact (timeout =
      ``quality_gate_failed``) without re-raising into the orchestrator.
    """
    try:
        completed = subprocess.run(  # noqa: S603  (shell=False; argv is a literal list)
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=_TIMEOUT_S,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        # Tooling missing (ruff / pytest not on PATH) — graceful degradation.
        return None
    except subprocess.TimeoutExpired as exc:
        # Treat timeout as a non-zero exit so QualityGate maps it to
        # quality_gate_failed (plan §5.4: gate failure must not crash the
        # pipeline).  Returncode 124 mirrors GNU ``timeout(1)``.
        return CmdResult(
            returncode=124,
            stdout_tail=_tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            stderr_tail=f"stage timed out after {_TIMEOUT_S}s",
        )

    return CmdResult(
        returncode=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def run_quality_gate(tools_dir: Path) -> QualityGateResult:
    """Run ``ruff check .`` then ``pytest -x`` in ``tools_dir``.

    Parameters
    ----------
    tools_dir:
        Directory the commands are launched from (passed as ``cwd=`` —
        we never shell-cd).  Must already exist.

    Returns
    -------
    QualityGateResult
        ``status`` is one of ``passed`` / ``quality_gate_failed`` /
        ``tooling_missing``.  ``ruff`` / ``pytest`` carry per-command tails
        when each stage ran (see :class:`QualityGateResult` for ``None``
        semantics).

    Notes
    -----
    Short-circuit: a non-zero ruff exit prevents pytest from running.
    """
    ruff_result = _run_stage(["ruff", "check", "."], cwd=tools_dir)
    if ruff_result is None:
        return QualityGateResult(
            status=GateStatus.TOOLING_MISSING.value,
            ruff=None,
            pytest=None,
        )

    if ruff_result["returncode"] != 0:
        # Short-circuit: do not run pytest when ruff fails.
        return QualityGateResult(
            status=GateStatus.QUALITY_GATE_FAILED.value,
            ruff=ruff_result,
            pytest=None,
        )

    pytest_result = _run_stage(["pytest", "-x"], cwd=tools_dir)
    if pytest_result is None:
        return QualityGateResult(
            status=GateStatus.TOOLING_MISSING.value,
            ruff=ruff_result,
            pytest=None,
        )

    if pytest_result["returncode"] != 0:
        return QualityGateResult(
            status=GateStatus.QUALITY_GATE_FAILED.value,
            ruff=ruff_result,
            pytest=pytest_result,
        )

    return QualityGateResult(
        status=GateStatus.PASSED.value,
        ruff=ruff_result,
        pytest=pytest_result,
    )
