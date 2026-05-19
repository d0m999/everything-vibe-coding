# TODOS

本仓 future work 登记处。每项含 What / Why / Pros / Cons / Context / 触发条件。

来源：`/plan-eng-review plan/orchestrator-mvp.md`（2026-05-19）的 Step 0 cross-reference + §5.6 v2 候选汇总。

---

## T-FUTURE-1 — 跨 step 并行（消费 plan-orchestrate Phase 4 waves）

- **What**：让 `tools/orchestrator.py` 读取 `plan.orchestrate.json` 的 `parallel_graph:{waves,deps}` 字段，把同一 wave 的 step 并发启动（每个 wave 内 fan-out N 个进程，wave 之间串行 barrier）。
- **Why**：plan-orchestrate skill Phase 4 已经计算出 DAG + waves，MVP 不消费是浪费。长 plan 的端到端时长能从 O(N) 压到 O(critical_path)。
- **Pros**：
  - 显著缩短端到端时长（典型 plan critical path ≈ 总 step 的 1/2 到 1/3）
  - 不改 plan-orchestrate skill（数据已在 JSON 里）
- **Cons**：
  - 调度复杂度 ↑（要管 wave barrier + 失败传播）
  - 并发 4-8 个 `claude -p` 进程对本地 API 配额 / rate limit 压力大
  - HANDOFF 串接逻辑要重新设计：同 wave 内 agent 间无 prior handoff，跨 wave 需要 join 上一波的多个 HANDOFF
- **Context**：plan §5.1 #3 已要求 `plan_md_to_json.py` 输出 `parallel_graph` 字段（forward compat），但 `orchestrator.py` MVP 忽略。当多 step plan 出现且 demo 跑 > 10 分钟时再做。
- **Depends on**：MVP 上线后稳定运行一段，HANDOFF 串接逻辑验证过。
- **Priority**: P3
- **Effort estimate**: human ~1 day / CC ~2-3 小时

---

## T-FUTURE-2 — reviewer-class 输出质量量化（eval）

- **What**：给 reviewer-class agent（`code-reviewer` / `security-reviewer` / `python-reviewer` / etc.）的 HANDOFF JSON 加结构化字段（`findings: [{severity, file, line, summary}]`），并写一套 eval 比对历史 baseline。
- **Why**：当前 reviewer 输出是自由文本 HANDOFF，无法量化哪个 reviewer / 哪轮 plan 改动后质量真的提升了。
- **Pros**：
  - 可对比迭代质量（"加了 Python 版本声明后，python-reviewer P1 finding 数下降 N%"）
  - 给 `severity: critical` 接入退出码（T-FUTURE-4）铺路
- **Cons**：
  - 改 reviewer agent 的 prompt 模板（在 `agents/*.md` 里）
  - eval baseline 建立成本高（要跑几十个 plan 攒数据）
- **Context**：依赖 reviewer-class 在 HANDOFF 里输出结构化 findings；MVP 不强制此字段。
- **Depends on**：T-FUTURE-4 设计先到位（决定 severity 如何映射）
- **Priority**: P3

---

## T-FUTURE-3 — `claude --resume <session-id>` 复用 process state

- **What**：探索 headless `claude -p --resume <prev-session-id>` 是否能让下一个 subagent 复用上一个的 process state（避免 cold start 60s/进程的开销）。
- **Why**：MVP 每个子进程都是 fresh cold start，demo 跑 4 分钟里大半是启动开销。
- **Pros**：
  - 若可行，端到端时长能压到 1/3
  - 与 T-FUTURE-1（跨 step 并行）正交，可叠加
- **Cons**：
  - headless 模式下 `--resume` 行为未文档化，需先用 throwaway demo 验
  - 复用 session 可能引入跨 agent 的 context 污染（违反"fresh per agent"原则）
- **Context**：plan §5.4 决策表明确"`--session-id` 仅作日志标签"，T-FUTURE-3 推翻这个假设需要先验。
- **Depends on**：先用 1-2 个 throwaway script 测 headless `--resume` 真实行为。
- **Priority**: P3

---

## T-FUTURE-4 — `--max-turns` 按 agent 类型分级

- **What**：把 `--max-turns` 从硬编码 40 改成按 agent 类型查表：`{reviewer: 20, impl: 60, design: 40, ...}`。
- **Why**：reviewer 通常 turn 少（20 足够），impl 类（`tdd-guide`）可能多（60 才够）。统一 40 浪费 reviewer 配额，对 impl 又不够保险。
- **Pros**：
  - token 用量更精确
  - 失败模式更可预测（reviewer 在 20 内不收敛就明显异常）
- **Cons**：
  - 配置面增加（agent 类型 → max-turns 映射表）
  - 跨 agent 类型迁移时要维护映射
- **Context**：MVP 硬编码 40 是 reasonable default；当 demo 跑出来反复触顶 max-turns 警告时再分级。
- **Priority**: P3

---

## T-FUTURE-5 — 中断恢复 / 断点续跑

- **What**：给 `orchestrator.py` 加 `--resume <run-id>` 入口，读 `.work/run-{ISO}/state.json`（新增），跳过已 passed 的 step，从 crashed / quality_gate_failed step 继续。
- **Why**：MVP 长 plan 跑一半挂了要从头来，浪费已 passed step 的产物。
- **Pros**：
  - 长 plan（10+ step）的迭代体验显著改善
  - 跟 Ralph outer-loop 的"取下一个 passes:false"语义对齐
- **Cons**：
  - 状态持久化要设计（哪些是幂等可重放的、哪些是副作用）
  - 中断时 transcript 可能写一半，要识别 partial 文件
- **Context**：MVP §5.6 已明确不做。当 plan §5.3 的实施顺序跑通 + demo 验证后，第一个真正大 plan 用上时再考虑。
- **Depends on**：T-FUTURE-1 之前做（先单线程稳定再加并行）
- **Priority**: P3

---

## T-FUTURE-6 — git worktree 隔离

- **What**：每个 step 在独立的 git worktree 里跑，避免 step 间互改同文件冲突。
- **Why**：MVP 所有 step 共享同一个 worktree，跨 step 并行（T-FUTURE-1）时会撞文件。
- **Pros**：
  - 启用真正的跨 step 并行（多个 worktree 同时写）
  - 失败回滚简单（删 worktree 即可）
- **Cons**：
  - worktree 创建 / 销毁开销
  - 跨 worktree 同步 HANDOFF / transcript 路径要协调
  - claude -p 在非主 worktree 的 cwd 下行为待验
- **Context**：T-FUTURE-1 跨 step 并行的前置条件。MVP 强顺序不需要。
- **Depends on**：T-FUTURE-1
- **Priority**: P3

---

## T-FUTURE-7 — `_extract_agent_fences` fence 边界约束文档化

- **What**：在 `tools/plan_md_to_json.py` `_extract_agent_fences` 的 docstring 中明确写出"步骤文本中所有 triple-backtick fence 均被视为 Agent fence；步骤文本内不应混入非 Agent code block（如 ` ```bash` 示例块）"。同时加一条测试锁定该行为：非 Agent fence 触发 `ParseError`。
- **Why**：fix-pass H3（commit `623920f`）把 fence regex 从 `r"\`\`\`\s*\n(.*?)\`\`\`"` 改成 `r"\`\`\`[^\n]*\n(.*?)\`\`\`"` 支持 language tag。副作用是任何带 language tag 的 fence（包括 ` ```bash`）都会被捕获，然后 `_extract_agent_fences` 因缺 `subagent_type=` 字段抛 `ParseError`。当前 spec 不允许步骤内混入非 Agent fence，所以不会触发，但约束未文档化。
- **Pros**：
  - 防止 future spec 扩展（如允许步骤里贴示例代码）时的意外 `ParseError`
  - 用测试锁定 contract，避免未来无意中"放宽"
- **Cons**：
  - 若 future spec 真要允许混入示例 fence，得改 regex 为更窄的 `r"\`\`\`(?:Agent|)\s*\n(.*?)\`\`\`"` 之类
- **Context**：来自 fix-pass code-reviewer（2026-05-19）的 MEDIUM finding。`tools/plan_md_to_json.py:159-179`。
- **Priority**: P3
- **Effort estimate**: CC ~20 分钟

---

## T-FUTURE-8 — parser 测试 fixture 复用减重

- **What**：新测试 1/2/3（`test_parse_mixed_tagged_and_bare_fences_both_extracted` / `test_step_without_tags_line_returns_empty_list` / `test_step_without_chain_line_returns_empty_string`）在 `tools/tests/test_plan_md_to_json.py` 第 958-1100 行各自携带完整 inline fixture，约 40 行重复。考虑抽出 `_make_full_md(steps=[...])` 工厂或让现有 `_make_step_md` 接受 `include_parallel_graph=True` 选项。
- **Why**：DRY；fixture 漂移时只需改一处。当前重复不影响正确性。
- **Pros**：
  - 减少 ~40 行重复
  - fixture 调整一次性生效
- **Cons**：
  - factory 接口设计要考虑各种 missing-field 排列组合
  - 过度参数化的 factory 比 inline 难读
- **Context**：fix-pass code-reviewer（2026-05-19）NIT。
- **Priority**: P4
- **Effort estimate**: CC ~30 分钟

---

## T-FUTURE-9 — H7 annotation 断言改用 `dep["deps"]` 引用

- **What**：`tools/tests/test_plan_md_to_json.py:391-392` 的 `assert "step-1" in dep["annotation"]` 依赖 `_REAL_DEMO_MD` fixture 文本恰好含 `"step-1"` 字面量。改为 `assert dep["deps"][0] in dep["annotation"]` 更通用，对 annotation 文本格式调整不敏感。
- **Why**：当前断言锁的是 fixture 文本巧合，不是 annotation 与 deps 的语义关系。若未来 annotation 格式从 `"heuristic: step-1 subject ..."` 改为 `"depends-on: step-1"` 仍通过，但若改为 `"heuristic: upstream-step-a"` 就静默失败。
- **Pros**：
  - 断言锁定语义而非 fixture 文本
  - 多 dep 场景下自动适配
- **Cons**：
  - 极小：当前精度已比原 `len > 0` 高出一截，再改是 incremental polish
- **Context**：fix-pass code-reviewer（2026-05-19）NIT。
- **Priority**: P4
- **Effort estimate**: CC ~5 分钟

---

## T-FUTURE-10 — `_RE_WAVE_ROW` 行尾锚定

- **What**：`tools/plan_md_to_json.py` `_RE_WAVE_ROW` 正则当前形如 `r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$"`（或类似无完整 `$` 锚定），理论上可在多管道符行中间匹配。加 `re.MULTILINE` 下严格的 `$` 行尾锚或换成更紧的 group。
- **Why**：现状下没 false match（waves 表格规整），属预防性收紧。本次 fix-pass 未触及。
- **Pros**：防御性更强
- **Cons**：现状无 bug，改动是 polish
- **Context**：fix-pass code-reviewer（2026-05-19）LOW，pre-existing 技术债，与本轮 fix 无关。
- **Priority**: P4
- **Effort estimate**: CC ~10 分钟
