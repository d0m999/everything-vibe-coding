"""Checkpoint B integration test:真跑一次 tools/orchestrator.py 子进程。

测试体：test_minimal_fixture_runs_real_subprocess
- 使用 tools/tests/fixtures/plan.orchestrate.minimal.json (1 step / 1 agent)
- fixture prompt 含 {{TARGET_FILE}} 占位符，运行时替换为 tmp_path 下预创建的绝对路径文件，
  让 Read tool_use 不依赖模型在不存在文件上的侥幸调用（HIGH-1 修复）
- QualityGate.run 通过 monkeypatch stub 返回 passed，避免嵌套 pytest 递归
- 6 项断言覆盖 CLI flag 验证 + stderr surface 路径

标记：@pytest.mark.integration — 需要真实 claude CLI，不在无网 CI 中跑。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# 注意：orchestrator 和 QualityGate 从 tools/ 导入，conftest 或 sys.path 负责配置
# ---------------------------------------------------------------------------
from orchestrator import GateResult, QualityGate, run_plan

# fixture 模板的绝对路径 — 不依赖 cwd；运行时会渲染 {{TARGET_FILE}} 占位符
_FIXTURE_TEMPLATE_PATH = Path(__file__).parent / "fixtures" / "plan.orchestrate.minimal.json"

# 错误关键词（大小写不敏感）— A4 断言用
_STDERR_BAD_PATTERNS = re.compile(
    r"error|traceback|auth|401|403|rate",
    re.IGNORECASE,
)

# 目标文件首行内容 — A3 验证 Read 工具调用，不验证 tool_result 是否成功
_TARGET_FILE_FIRST_LINE = "step-8 fixture target line"
_TARGET_FILE_CONTENT = f"{_TARGET_FILE_FIRST_LINE}\nsecond line for body\n"


@pytest.mark.integration
def test_minimal_fixture_runs_real_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真跑 claude -p 子进程，验证 5 项断言全部通过。

    QualityGate.run 被 stub 为 passed，防止嵌套 pytest 无限递归。
    """
    # --- stub QualityGate.run：避免嵌套 pytest 调用 ---
    def _gate_stub(self: Any) -> GateResult:  # noqa: ANN401
        return GateResult(status="passed", stdout="stubbed by test", stderr="")

    monkeypatch.setattr(QualityGate, "run", _gate_stub)

    # --- HIGH-1 修复：预创建目标文件 + 渲染 fixture 模板，注入绝对路径 ---
    target_file = tmp_path / "checkpoint_b_target.txt"
    target_file.write_text(_TARGET_FILE_CONTENT, encoding="utf-8")
    assert target_file.exists(), f"setup: target_file 未创建: {target_file}"

    template_text = _FIXTURE_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "{{TARGET_FILE}}" in template_text, (
        "setup: fixture 模板必须含 {{TARGET_FILE}} 占位符"
    )
    rendered_text = template_text.replace("{{TARGET_FILE}}", str(target_file))
    runtime_fixture = tmp_path / "plan.orchestrate.runtime.json"
    runtime_fixture.write_text(rendered_text, encoding="utf-8")

    # --- run_plan 在 tmp_path 下创建 .work/run-* ---
    monkeypatch.chdir(tmp_path)
    exit_code = run_plan(runtime_fixture)

    # --- 找到唯一 run 目录 ---
    run_dirs = list((tmp_path / ".work").glob("run-*"))
    assert len(run_dirs) == 1, (
        f"Expected exactly 1 run-* directory, found {len(run_dirs)}: {run_dirs}"
    )
    run_dir = run_dirs[0]
    step_dir = run_dir / "step-1"

    # --- 找 .jsonl 文件 ---
    jsonl_files = list(step_dir.glob("agent-1-echo-reader.jsonl"))
    assert len(jsonl_files) == 1, (
        f"Expected agent-1-echo-reader.jsonl in {step_dir}, found: {list(step_dir.iterdir())}"
    )
    jsonl_path = jsonl_files[0]

    # --- 找 .stderr.log 文件 ---
    stderr_path = step_dir / "agent-1-echo-reader.stderr.log"
    assert stderr_path.exists(), f"Expected {stderr_path} to exist"

    # -----------------------------------------------------------------------
    # A1: .jsonl 行格式 — 逐行 json.loads 不抛异常，且行数 >= 2
    # -----------------------------------------------------------------------
    raw_text = jsonl_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    assert len(lines) >= 2, (
        f"A1 FAIL: .jsonl 应有 >= 2 行，实际 {len(lines)} 行。内容:\n{raw_text[:500]}"
    )
    parsed_lines: list[dict] = []
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"A1 FAIL: 第 {i+1} 行无法 json.loads: {exc}\n行内容: {line[:200]!r}")
        parsed_lines.append(obj)

    # -----------------------------------------------------------------------
    # A2: 至少一行 type == "assistant"
    # -----------------------------------------------------------------------
    assistant_lines = [obj for obj in parsed_lines if obj.get("type") == "assistant"]
    assert len(assistant_lines) >= 1, (
        f"A2 FAIL: 未找到 type='assistant' 的行。所有 type 值: "
        f"{[obj.get('type') for obj in parsed_lines]}"
    )

    # -----------------------------------------------------------------------
    # A3: assistant 行的 message.content[*] 里有 {type: tool_use, name: Read}
    #     这是 --allowedTools 生效的硬证据
    # -----------------------------------------------------------------------
    found_read_tool_use = False
    for obj in assistant_lines:
        message = obj.get("message", {})
        content_list = message.get("content", [])
        if isinstance(content_list, list):
            for block in content_list:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Read"
                ):
                    found_read_tool_use = True
                    break
        if found_read_tool_use:
            break

    assert found_read_tool_use, (
        "A3 FAIL: 未在 assistant 行的 message.content 里找到 {type: tool_use, name: Read}。\n"
        "--allowedTools 可能未生效，或模型未调用 Read 工具。\n"
        f"assistant 行数: {len(assistant_lines)}\n"
        f"前 3 行内容: {json.dumps(assistant_lines[:3], ensure_ascii=False)[:800]}"
    )

    # -----------------------------------------------------------------------
    # A4: .stderr.log 空或仅 info — 不含错误关键词
    # -----------------------------------------------------------------------
    stderr_text = stderr_path.read_text(encoding="utf-8")
    if stderr_text.strip():
        bad_match = _STDERR_BAD_PATTERNS.search(stderr_text)
        assert bad_match is None, (
            f"A4 FAIL: .stderr.log 含错误关键词 {bad_match.group()!r}。\n"
            f"stderr 全文:\n{stderr_text[:1000]}"
        )

    # -----------------------------------------------------------------------
    # A5: summary.json 存在且 steps[0].status == "passed"
    # -----------------------------------------------------------------------
    summary_path = run_dir / "summary.json"
    assert summary_path.exists(), f"A5 FAIL: summary.json 不存在于 {run_dir}"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    steps_in_summary = summary.get("steps", [])
    assert len(steps_in_summary) >= 1, "A5 FAIL: summary.json 的 steps 列表为空"
    first_step_status = steps_in_summary[0].get("status")
    assert first_step_status == "passed", (
        f"A5 FAIL: summary.json steps[0].status = {first_step_status!r}，期望 'passed'。\n"
        f"完整 summary: {json.dumps(summary, ensure_ascii=False, indent=2)}"
    )

    # run_plan 也应返回 0（all passed）
    assert exit_code == 0, (
        f"A5 FAIL: run_plan() 返回 {exit_code}，期望 0。"
    )

    # -----------------------------------------------------------------------
    # A4b (HIGH-2 修复): stderr 文件状态与 summary.json 中 stderr_warnings 一致
    #
    # orchestrator.StepRunner 在 ProcessResult.stderr_nonempty=True 时追加
    # "agent-{K}-{name}: non-empty stderr" warning 到 summary。这条断言覆盖
    # ProcessRunner → StepRunner → summary.json 的生产 surface 路径。
    # -----------------------------------------------------------------------
    stderr_file_nonempty = bool(stderr_text)
    warnings_in_summary = steps_in_summary[0].get("stderr_warnings", [])
    warning_for_this_agent = any(
        "agent-1-echo-reader" in w and "non-empty stderr" in w
        for w in warnings_in_summary
    )
    assert stderr_file_nonempty == warning_for_this_agent, (
        "A4b FAIL: stderr 文件状态与 summary.json stderr_warnings 不一致。\n"
        f"  stderr 文件非空: {stderr_file_nonempty}\n"
        f"  summary warning 命中: {warning_for_this_agent}\n"
        f"  summary stderr_warnings: {warnings_in_summary!r}\n"
        f"  stderr 文件内容: {stderr_text[:300]!r}"
    )
