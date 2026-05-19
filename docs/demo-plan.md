# Demo Plan — orchestrator MVP smoke

这是 orchestrator MVP 的最小可跑 demo plan，目的是验证 `/plan-orchestrate` 能正确识别 step、推断 tag（impl / test）、并把它们排成串行链。参考设计见 [plan/orchestrator-mvp.md](../plan/orchestrator-mvp.md)。

## Step 1 — 实现 add 函数

Intent: 在 `tools/demo/util.py` 文件中创建并实现一个 `add(a: int, b: int) -> int` 加法函数。整个函数应该使用 Python 编写、简洁清晰，确保交付物能被后续单元测试引用。

Acceptance:
- 函数签名为 `add(a: int, b: int) -> int`，明确返回两数之和
- 正常返回值对（正数 + 正数）、边界值（0、负数）、大数加法都正确
- 文件 `tools/demo/util.py` 创建完毕、import 可用

## Step 2 — 给 add 函数写 pytest 单元测试

Intent: 为 Step 1 实现的 `tools/demo/util.py` 中的 `add` 函数编写完整的 pytest 单元测试，测试覆盖率应达到 100%。

Acceptance:
- 测试文件位置为 `tests/demo/test_util.py`，pytest 能直接运行
- 用例数 ≥5，覆盖正常情况、零值、负数和边界场景
- 所有用例通过，coverage 百分比 ≥95%
