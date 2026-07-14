# Local Patches

> 对 vendored 文件的本地修改清单。每行格式：日期 | 文件路径 | 修改概要 | 原因。
>
> 用途：将来从上游同步新版本时识别需要 re-apply 的修改点。

## 2026-07-14 — 存量悬空引用清理（226 行 → 98 行）

对 2026-05-16 vendoring 时就存在、此前一直"接受现状"未处理的悬空引用做了一轮系统清理。
`scripts/check-references.sh` 命中从 226 行 / 76 个 drop 名字降到 98 行 / 13 个 drop 名字；
剩余 13 个全部是假阳性或对真实本地事物的正确指代，见 `docs/UPSTREAM.md`。

补 vendor（用户确认）：

| 日期 | 文件 | 修改 | 原因 |
|---|---|---|---|
| 2026-07-14 | `skills/{swiftui-patterns,swift-concurrency-6-2,swift-actor-persistence,swift-protocol-di-testing,foundation-models-on-device,liquid-glass-design}/` | 从 ECC 补 vendor Swift 六件套（`liquid-glass-design` 从 `attic/` 移回，其余 5 个全新拷贝），加入 `scripts/vendor-from-ecc.sh` 的 `SKILLS` 数组 | 用户做 iOS 开发；`swift-reviewer`/`swift-build-resolver` 正文已引用这些 skill；`docs/ECC-DRIFT-AUDIT.md` §5 标记为最高优先级缺口；零外部依赖 |
| 2026-07-14 | `scripts/vendor-from-ecc.sh` | 修复 `insert_source_comment()`：Source 注释改为插入 frontmatter 闭合 `---` 之后（而非文件开头），agents 类型完全跳过注释插入 | 沿用旧逻辑会重现 `887eac6` 那次修过的 bug（注释在 frontmatter 前会让 agent/skill loader 读不到 frontmatter）；这次新 vendor 的 5 个 Swift skill 已用旧逻辑生成过一次并手工修正 |

删引用，改指向本仓库真实存在的 agent/command/skill（默认走这条）：

| 日期 | 文件 | 修改 | 原因 |
|---|---|---|---|
| 2026-07-14 | `skills/prompt-optimizer/SKILL.md` | 重写 Phase 3 的 By-Intent / By-Tech-Stack 表、Section 2-4 示例、Related Components；删除 `tdd-workflow`/`e2e-testing`/`blueprint`/`search-first`/`configure-ecc`/`cost-aware-llm-pipeline` 等 68 处不存在组件引用，删除 Java/Kotlin/Perl/C++/Go 等 v1 未覆盖语言行 | 全仓库命中最多的单文件（占总数 30%）；核心是一张"意图→组件"推荐矩阵，矩阵推荐的组件一半不存在 |
| 2026-07-14 | `skills/mle-workflow/SKILL.md` | 修复 Related Skills、Reuse-the-SWE-Surface 表、Ten-MLE-Task-Simulations 表；`tdd-workflow`→`tdd-guide`，`e2e-testing`/`browser-qa`→`e2e-runner`(或 gstack `/qa`)，`clickhouse-io`/`backend-patterns`/`dashboard-builder`/`product-capability`/`feature-dev`/`github-ops`/`opensource-pipeline`/`dmux-workflows`/`code-tour`/`token-budget-advisor`/`cost-aware-llm-pipeline`/`search-first` 等改为本仓库真实存在的等价物或纯文字描述 | 第二大命中文件（30 处） |
| 2026-07-14 | `commands/plan-orchestrate.md` | 从 Available-agent-catalogue 和 Phase 0/2 的 `py_sub`/`lang` 解析表中移除已归档的 `django-reviewer`/`django-build-resolver`/`rust-reviewer`/`rust-build-resolver`，归并到 generic 回退路径；更新 Not-in-catalogue 排除清单 | `django-*`/`rust-*` 两套 agent 已被 `071d3d9` 归档到 `attic/`（v1 主动裁剪），但这个文件的 py_sub/lang 解析逻辑没跟着更新，会 emit 出已不存在的 agent 名字 |
| 2026-07-14 | `commands/plan.md`、`commands/plan-prd.md` | `tdd-workflow` skill → `tdd-guide` agent；`/pr`、`/prp-pr` → `gh pr create`（或 gstack `/ship`）；删除指向 `/prp-plan`/`/prp-implement` 的 legacy PRP 流程提示 | `/pr`/`/prp-pr`/`/prp-plan`/`/prp-implement` 都是 ECC 命令，本仓库均未 vendor，且没有 `.claude/PRPs/` 这套本地约定 |
| 2026-07-14 | `commands/hookify.md` | `/hookify` 零参数路径从"调用 `conversation-analyzer` agent"改为"直接读回当前对话" | `conversation-analyzer` 从未 vendor（`docs/ECC-DRIFT-AUDIT.md` §3.3 已记录此断链）；改为让 Claude 自己分析对话，不再依赖不存在的子 agent |
| 2026-07-14 | `agents/tdd-guide.md`、`agents/e2e-runner.md`、`commands/python-review.md`、`skills/strategic-compact/SKILL.md`（2 处） | `tdd-workflow`/`e2e-testing` 引用改为指向 `tdd-guide`/`e2e-runner` agent 或 gstack `/qa` | 用户明确选择：不补 vendor 这两个 skill，仓库已有对应 agent 就够用 |
| 2026-07-14 | `agents/typescript-reviewer.md`、`skills/coding-standards/SKILL.md`、`skills/postgres-patterns/SKILL.md`、`skills/redis-patterns/SKILL.md` | 删除 `backend-patterns`、`clickhouse-io`、`django-patterns` 引用 | 三者均未 vendor（`clickhouse-io`/`django-patterns` 已被 `071d3d9` 归档），且没有 1:1 本地替代品，直接删引用 |
| 2026-07-14 | `skills/agent-introspection-debugging/SKILL.md` | `council`/`workspace-surface-audit` 建议改为"直接问用户"/"用 `git status`/`git diff` 审查工作区" | 两者均未 vendor 且无直接等价物，改写为不依赖具名组件的可执行指令 |
| 2026-07-14 | `skills/canary-watch/SKILL.md`、`skills/continuous-agent-loop/SKILL.md` | `/browser-qa`→gstack `/qa`；`/quality-gate`（伪装成 slash command）→明确是自动 hook；`nanoclaw-repl`→改写为"内置 context compaction + strategic-compact" | 前二者未 vendor，第三者原表述把一个自动运行的 hook 误写成了可调用的 slash command |
| 2026-07-14 | `skills/skill-comply/SKILL.md`、`skills/skill-scout/SKILL.md`、`skills/autonomous-loops/SKILL.md` | 示例/Related 里的 `search-first`/`agent-sort`/`article-writing`/`content-engine` 换成本仓库真实存在的 `documentation-lookup`/`repo-scan`/`verification-loop`；`CLAW_SKILLS=tdd-workflow` 示例值换成 `verification-loop` | 这些是文档里的示例/参考清单，换成真实存在的名字之后示例本身也更可信 |

接受现状（假阳性，详见 `docs/UPSTREAM.md`）：`sessions`(34)、`projects`(28)、`checkpoint`(12)、`promote`(5)、`benchmark`(4) 是通用英文词撞名；
`tdd-workflow`(3，仅剩 `skill-comply` 测试 fixture 内部 id) 是本仓库自己的标识符；`quality-gate`(2)、`git-workflow`(1) 是对真实本地 hook/rules 文件的正确指代；
`chief-of-staff`(1)、`django-reviewer`/`django-build-resolver`(2+2)、`rust-reviewer`/`rust-build-resolver`(2+2) 都出现在 `plan-orchestrate.md` 故意的"不要 emit 这些名字"排除清单里，命中是预期行为。

未补 vendor、也未改写的已知缺口（留给下一轮，不在本次范围内）：`skills/autonomous-loops/SKILL.md` 的"NanoClaw REPL"整节描述的是 ECC 自带的 `scripts/claw.js`，本仓库从未 vendor 这个脚本，整节功能实际不可用（只做了示例值的最小修复，没有决定"补 vendor 还是删整节"）。

## 2026-06-16 — Codex skill frontmatter 兼容

| 日期 | 文件 | 修改 | 原因 |
|---|---|---|---|
| 2026-06-16 | `skills/*/SKILL.md` | 将首行 `<!-- Source: ... -->` 移到 YAML frontmatter 之后 | Codex 只会发现以 frontmatter 开头的 `SKILL.md`；保留来源元数据，同时让逐项 symlink 到 `~/.codex/skills` 后可被 Codex 加载 |
| 2026-06-16 | `commands/*.md` | 将首行 `<!-- Source: ... -->` 移到 YAML frontmatter 之后 | Codex custom prompts 也需要以 frontmatter 开头；让逐项 symlink 到 `~/.codex/prompts` 后可显示描述和参数提示 |
| 2026-06-16 | `commands/local/ralph-init.md` | 将硬编码 `~/.claude/commands/ralph-init` 改成 Claude/Codex 双路径资源目录说明 | `ralph-init` 在 Codex 中通过 `~/.codex/prompts/ralph-init` 提供参考文件和校验脚本 |
| 2026-06-16 | `scripts/generate-codex-command-skills.sh` / `.agents/skills/evc-command-*` | 为每个 `commands/*.md` 生成 thin skill wrapper，安装到 `~/.codex/skills/evc-command-*` | Codex 的 `$` picker 只显示 skills；gstack 也是用 skill wrapper 承载 `/qa`、`/review` 这类命令感入口 |

## 2026-05-16 — v1 vendoring dangling refs 清理

`scripts/check-references.sh` 扫描发现 74 个 drop 名字在 vendored 文件中被引用。按「count ≥ 2 + 有 1:1 替代品」筛选，做了 6 处 sed 替换：

| 日期 | 文件 | 修改 | 原因 |
|---|---|---|---|
| 2026-05-16 | `agents/build-error-resolver.md:117` | `` `architect` `` → `` `code-architect` `` | ecc 已重命名 architect 为 code-architect（v1 keep） |
| 2026-05-16 | `skills/prompt-optimizer/SKILL.md:128-130` | `architect` (3 处) → `code-architect` | 同上 |
| 2026-05-16 | `agents/mle-reviewer.md:45` | `` `e2e-runner` `` → `` gstack `/qa` `` | v1 决定 E2E 走 gstack /qa（SELECTION-v1.md 横向去重） |
| 2026-05-16 | `skills/prompt-optimizer/SKILL.md:125` | `e2e-runner` (表格) → `/qa (gstack)` | 同上 |

替换方式（命令记录，便于复现）：

```bash
sed -i.bak -E 's/(^|[^a-z0-9_-])architect([^a-z0-9_-]|$)/\1code-architect\2/g' \
  agents/build-error-resolver.md skills/prompt-optimizer/SKILL.md

sed -i.bak -E 's/`e2e-runner`/gstack `\/qa`/g' agents/mle-reviewer.md
sed -i.bak -E 's/(^|[^a-z0-9_-])e2e-runner([^a-z0-9_-]|$)/\1\/qa (gstack)\2/g' \
  skills/prompt-optimizer/SKILL.md
```

`.bak` 文件已删除；`.gitignore` 增加 `*.bak` 防止以后误提交。

## 未处理的 dangling refs（接受现状）— 状态见上方 2026-07-14 章节

> **2026-07-14 更新**：本节记录的是 2026-06-16 时点的快照。绝大多数条目已在上方
> "2026-07-14 — 存量悬空引用清理" 一节处理完毕（删引用或补 vendor）；剩余仍然
> 有效的假阳性列表见 `docs/UPSTREAM.md`。以下内容保留作历史记录，不再代表当前状态。

`scripts/check-references.sh` 还报告了 ~68 个其他 drop 名字被引用（合计 ~328 行），主要类别：

- **可能假阳性（高 count，普通词）**：`projects` 87 / `sessions` 59 / `promote` 19 / `tdd-workflow` 15 / `checkpoint` 12 / `blueprint` 12
- **被 drop 的语言整套**（无 1:1 替代品）：`go-*`、`kotlin-*`、`java-*`、`cpp-*`、`perl-*`、`springboot-*`、`quarkus-*`、`jpa-patterns`、`golang-*`、`android-clean-architecture`、`compose-multiplatform-patterns`
- **被 drop 的工作流工具**：`conversation-analyzer`、`opensource-pipeline`、`prp-implement`、`prp-plan`、`feature-dev`、`project-init`、`save-session`、`resume-session`、`instinct-*`、`council`、`nanoclaw-repl`、`dmux-workflows`、`agent-sort` 等
- **被 drop 的 skill 概念**：`workspace-surface-audit`、`token-budget-advisor`、`iterative-retrieval`、`search-first`、`cost-tracking`、`cost-aware-llm-pipeline`、`product-capability`、`browser-qa`、`dashboard-builder`、`content-engine`、`code-tour`、`benchmark`、`article-writing`、`backend-patterns`、`rust-patterns`、`rust-testing`、`quality-gate`、`e2e-testing`、`git-workflow`、`github-ops`、`configure-ecc`、`video-editing`、`swiftui-patterns`、`swift-concurrency-6-2`、`swift-actor-persistence`、`swift-protocol-di-testing`

这些 dangling 引用：

- **不阻塞 install** — 是文本提及而非真实 Agent tool 调用
- 影响仅当 Claude 读到这些文档并误尝试调用 drop 名字时 → 冷启动期 4 周观察，case-by-case 修
- 不预先批量改 — 避免无替代品的强行 sed 引入语义错误

## How to add a new local patch entry

When you modify a vendored file:

1. (Optional) Add an HTML comment at the top of the file, right after the `<!-- Source: ... -->` line:
   ```html
   <!-- Local patch: 2026-MM-DD — <one-line reason> -->
   ```
2. Append a row to the table in the current section above.
