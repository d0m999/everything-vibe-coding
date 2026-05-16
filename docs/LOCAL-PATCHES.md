# Local Patches

> 对 vendored 文件的本地修改清单。每行格式：日期 | 文件路径 | 修改概要 | 原因。
>
> 用途：将来从上游同步新版本时识别需要 re-apply 的修改点。

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

## 未处理的 dangling refs（接受现状）

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
