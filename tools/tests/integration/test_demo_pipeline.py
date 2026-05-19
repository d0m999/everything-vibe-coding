"""Step 11 end-to-end integration test: demo-plan → JSON → orchestrator → summary.

Pipeline shape (plan §5.2 + plan §5.3 step 11)::

    docs/plan-orchestrate-output.md   (pre-saved /plan-orchestrate output)
        │  plan_md_to_json.parse_file()
        ▼
    plan.orchestrate.json (2 steps × 2 agents)
        │  orchestrator.run_plan()
        ▼
    .work/run-{ISO}/
        ├── step-1/agent-{1,2}-*.jsonl + .stderr.log
        ├── step-2/agent-{1,2}-*.jsonl + .stderr.log
        └── summary.json

Why use the pre-saved markdown fixture
--------------------------------------
The plan-orchestrate skill is generative-only and stochastic. Re-running it in
the test would add ~60 s of latency and make the test flaky. The committed
``docs/plan-orchestrate-output.md`` is the canonical real output from running
``/plan-orchestrate @docs/demo-plan.md`` (plan §5.3 step 4, Checkpoint A).
This still exercises the real ``plan_md_to_json.parse_file()`` parser.

QualityGate stubbing
--------------------
``QualityGate.run`` is monkeypatched to return ``passed`` to avoid nested
``pytest -x`` recursion (same pattern as ``test_fixture_run_e2e.py``). The
quality gate's actual behaviour is covered by ``test_quality_gate.py``.

Budget
------
Hard ceiling 240 s (plan §5.5 P1): 2 steps × 2 agents × ~60 s/process.

Markers
-------
``@pytest.mark.integration`` keeps the test out of the default ``pytest -x``
run (see ``tools/pyproject.toml`` ``addopts``). Opt in with
``pytest -m integration``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from orchestrator import GateResult, QualityGate, run_plan
from plan_md_to_json import MISSING_HANDOFF_PLACEHOLDER, parse_file

# Repo layout: tools/tests/integration/<this> → repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLAN_MD_PATH = _REPO_ROOT / "docs" / "plan-orchestrate-output.md"

# Hard wall-clock budget for the full 4-subprocess pipeline.
_BUDGET_SECONDS = 240.0

# Splice prefix that StepRunner injects into every non-first agent prompt.
_HANDOFF_PREFIX = "[Prior HANDOFF from "


@pytest.mark.integration
def test_demo_pipeline_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: parse markdown → run plan → assert summary + HANDOFF + console."""
    # --- guard: prerequisite fixture is committed ---
    assert _PLAN_MD_PATH.exists(), (
        f"prerequisite fixture missing: {_PLAN_MD_PATH} "
        "(should be the committed /plan-orchestrate output for docs/demo-plan.md)"
    )

    # --- stub QualityGate to avoid nested `pytest -x` recursion ---
    def _gate_stub(self: Any) -> GateResult:  # noqa: ANN401
        return GateResult(status="passed", stdout="stubbed by integration test", stderr="")

    monkeypatch.setattr(QualityGate, "run", _gate_stub)

    # --- (1) real parse of the committed markdown ---
    plan = parse_file(_PLAN_MD_PATH)
    assert len(plan["steps"]) == 2, (
        f"fixture should describe 2 steps, found {len(plan['steps'])}"
    )
    for step in plan["steps"]:
        assert len(step["agents"]) == 2, (
            f"step-{step['id']} expected 2-agent chain, found {len(step['agents'])}"
        )

    plan_json_path = tmp_path / "plan.orchestrate.json"
    plan_json_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # --- (2) run orchestrator under tmp_path so .work/ + any file writes
    #         are sandboxed (tmp_path is auto-cleaned by pytest) ---
    monkeypatch.chdir(tmp_path)

    t_start = time.monotonic()
    exit_code = run_plan(plan_json_path)
    elapsed = time.monotonic() - t_start

    # --- timing assertion (hard) ---
    assert elapsed < _BUDGET_SECONDS, (
        f"pipeline took {elapsed:.1f}s, exceeds {_BUDGET_SECONDS:.0f}s budget "
        "(plan §5.5 P1: 2 steps × 2 agents × ~60s)"
    )

    # --- exit code is one of the documented values (plan §6) ---
    assert exit_code in (0, 1, 2), f"unexpected exit code {exit_code}"

    # --- (3) summary.json structure ---
    run_dirs = list((tmp_path / ".work").glob("run-*"))
    assert len(run_dirs) == 1, (
        f"expected exactly 1 run-* dir under .work/, found {run_dirs}"
    )
    run_dir = run_dirs[0]

    summary_path = run_dir / "summary.json"
    assert summary_path.exists(), f"summary.json missing under {run_dir}"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary.get("run_dir") == str(run_dir), (
        f"summary.run_dir should be {run_dir!s}, got {summary.get('run_dir')!r}"
    )
    assert summary.get("iso_timestamp"), "summary.iso_timestamp missing"

    steps_in_summary = summary.get("steps", [])
    assert len(steps_in_summary) == 2, (
        f"summary should contain 2 step records, found {len(steps_in_summary)}"
    )

    valid_statuses = {"passed", "quality_gate_failed", "crashed"}
    for entry in steps_in_summary:
        assert entry.get("step_id") in (1, 2), f"unexpected step_id: {entry!r}"
        assert entry.get("title"), f"step {entry.get('step_id')} missing title"
        assert entry.get("status") in valid_statuses, (
            f"step {entry.get('step_id')} status={entry.get('status')!r} "
            f"not in {sorted(valid_statuses)}"
        )
        assert isinstance(entry.get("stderr_warnings"), list), (
            f"step {entry.get('step_id')} stderr_warnings must be a list"
        )

    # --- (4) HANDOFF propagation: at least one agent-2 prompt got the
    #         spliced "[Prior HANDOFF from <prev>: <...>]" prefix and
    #         the spliced content was NOT the missing-handoff placeholder.
    #
    # The user prompt sent to claude -p is echoed back in the stream-json
    # transcript as a {type: "user"} event. The orchestrator prepends the
    # splice prefix when agent_index > 1 (see orchestrator.StepRunner.run_step).
    handoff_propagated = False
    propagated_evidence: list[str] = []

    for step in plan["steps"]:
        step_id = step["id"]
        second_agent = step["agents"][1]
        agent2_name = second_agent["name"]
        agent2_jsonl = run_dir / f"step-{step_id}" / f"agent-2-{agent2_name}.jsonl"
        if not agent2_jsonl.exists():
            continue

        for raw_line in agent2_jsonl.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "user":
                continue
            # The user message may carry content as a plain string OR a list of
            # blocks; serialize the whole thing and substring-match.
            blob = json.dumps(event.get("message", {}), ensure_ascii=False)
            if _HANDOFF_PREFIX not in blob:
                continue
            if MISSING_HANDOFF_PLACEHOLDER in blob:
                propagated_evidence.append(
                    f"step-{step_id} agent-2 received PLACEHOLDER (chain degraded)"
                )
                continue
            handoff_propagated = True
            propagated_evidence.append(
                f"step-{step_id} agent-2 prompt carries [Prior HANDOFF from ...]"
            )
            break
        if handoff_propagated:
            break

    assert handoff_propagated, (
        "no agent-2 prompt carried a non-placeholder HANDOFF; "
        "chain handoff is the core MVP contract.\n"
        f"evidence: {propagated_evidence!r}\n"
        f"run_dir: {run_dir}"
    )

    # --- (5) console summary table was printed (capsys) ---
    captured = capsys.readouterr()
    assert "Orchestrator run complete" in captured.out, (
        f"console summary header missing from stdout. stdout head:\n"
        f"{captured.out[:500]!r}"
    )
    assert "Status" in captured.out and "Title" in captured.out, (
        "console summary table columns missing"
    )
    assert f"Summary written to: {summary_path}" in captured.out, (
        "summary path footer not surfaced to console"
    )

    # --- (6) stderr surface contract: any non-empty stderr.log on disk must
    #         appear as a warning in summary.json (plan §5.4 A2). This guards
    #         against silently swallowed auth / rate-limit / network errors.
    for step in plan["steps"]:
        step_id = step["id"]
        step_dir = run_dir / f"step-{step_id}"
        for agent_index, agent in enumerate(step["agents"], start=1):
            stderr_log = step_dir / f"agent-{agent_index}-{agent['name']}.stderr.log"
            if not stderr_log.exists():
                continue
            if not stderr_log.read_text(encoding="utf-8").strip():
                continue
            # non-empty stderr → must show up as a warning for this step
            warnings_for_step = next(
                (s["stderr_warnings"] for s in steps_in_summary if s["step_id"] == step_id),
                [],
            )
            assert any(
                f"agent-{agent_index}-{agent['name']}" in w and "non-empty stderr" in w
                for w in warnings_for_step
            ), (
                f"step-{step_id} agent-{agent_index}-{agent['name']} stderr is "
                f"non-empty but no warning was surfaced to summary.json. "
                f"warnings_for_step: {warnings_for_step!r}"
            )
