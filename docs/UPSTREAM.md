# Upstream Name Collisions (Accepted False Positives)

> `scripts/check-references.sh` 用简单子串匹配扫描 vendored 文件里对 ECC drop-list 名字的引用。
> 本文档记录被判定为**假阳性**、刻意保留不修改的命中 —— 要么是撞上了 ECC 组件名的通用英文词，
> 要么是本仓库自己代码/测试里的内部标识符，要么是对真实存在的本地事物的正确指代。
> 与之相对的"真悬空引用"修复记录见 `docs/LOCAL-PATCHES.md`。

生成于 2026-07-14，对应 `bash scripts/check-references.sh --verbose` 清理后的剩余命中（13 个 drop 名字，93 行）。

> 数字必须用**干净 checkout** 复现（`git worktree add` 一个 detached HEAD 再跑）。早先版本记的
> 98 行 / `sessions`=34 / `projects`=28 / `promote`=5 是在脏工作区量的：当时脚本会把 gitignored 的
> `__pycache__/*.pyc` 当成 "Binary file matches" 计入命中，数字因此取决于谁的机器在跑。
> `check-references.sh` 现已加 `-I --exclude-dir=__pycache__`（等）堵掉这个口子，脏/净工作区结果一致。

## 通用词撞名（高 count，非组件引用）

这些 drop 名字确实是 ECC 里的真实组件名（`/sessions`、`/projects`、`/checkpoint`、`/promote` 是 ECC 命令；
`benchmark` 是 gstack 的 skill），但本仓库里的每一处命中都是在用它们的**字面英文含义**，不是在调用对应组件：

| 名字 | count | 典型命中 | 为什么是假阳性 |
|---|---|---|---|
| `sessions` | 32 | "Claude Code sessions", "long sessions", "across sessions" | 全部是"会话"这个词的自然语言用法，没有一处是 `/sessions` 命令调用 |
| `projects` | 26 | "across projects", "data/projects/\*.json", "Global skills (all projects)" | 全部是"项目"这个词或本地路径片段，没有一处是 `/projects` 命令调用 |
| `checkpoint` | 12 | PyTorch `torch.load(checkpoint)`、"mental checkpoint"、git 场景的检查点 | 全部是训练检查点/口语检查点，没有一处是 `/checkpoint` 命令调用 |
| `promote` | 4 | Python 变量名 `promote = []`（`skill-comply/scripts/report.py`）、"Vercel: promote previous deployment" | 全部是英文动词或代码变量名，没有一处是 `/promote` 命令调用 |
| `benchmark` | 4 | "benchmark score"（选库时的匹配度打分）、`torch.backends.cudnn.benchmark`、"CIS AWS Foundations Benchmark" | 全部是"基准/评分"这个词的自然语言或第三方 API 用法，不是 gstack `/benchmark` skill |

## 本仓库内部标识符（非外部引用）

| 位置 | 命中 | 为什么是假阳性 |
|---|---|---|
| `skills/skill-comply/fixtures/tdd_spec.yaml:1`、`skills/skill-comply/tests/test_grader.py:137`、`skills/skill-comply/tests/test_parser.py:58` | `tdd-workflow` (3) | 这是 skill-comply 自己的测试 fixture 的内部 spec id（`source_rule: rules/common/testing.md`），验证的是"agent 有没有遵循 TDD 工作流程"，不依赖任何叫 `tdd-workflow` 的 skill 文件存在。改这个 id 纯粹是测试churn，没有实际收益 |

## 对真实本地事物的正确指代（字面撞名，指向真实存在）

| 位置 | 命中 | 指向的真实事物 |
|---|---|---|
| `skills/mle-workflow/SKILL.md:51`、`skills/continuous-agent-loop/SKILL.md:30` | `quality-gate` (2) | `hooks/quality-gate.js` —— 本仓库自研的 PostToolUse hook（比 ECC 版本更强，见 `docs/ECC-DRIFT-AUDIT.md` §2），两处都已改写为"the quality-gate hook, which runs automatically on Write/Edit"，明确说明这是自动 hook 不是 slash command |
| `skills/skill-comply/SKILL.md:22` | `git-workflow` (1) | 用户全局 rules 里的 `rules/common/git-workflow.md`（不在本仓库 tree 内，但在 `~/.claude/rules/common/` 真实存在），这里只是在举例"Rules 类目录下有哪些规则文件"，不是在调用一个不存在的 ECC skill |
| `commands/plan-orchestrate.md:119,135,186,193` | `chief-of-staff` (1)、`django-reviewer` / `django-build-resolver` (2+2)、`rust-reviewer` / `rust-build-resolver` (2+2) | 这些都出现在**故意的排除清单**里（"Not in this catalogue (do not emit)"），Django/Rust 两套 agent 已被 `071d3d9` 归档到 `attic/`（v1 主动裁剪，见 `docs/SELECTION-v1.md`），这几行的作用正是提醒模型"不要 emit 这些名字"—— 命中是预期行为，不是 bug |

## 处理原则

- 以上 13 个名字、93 行命中**保持原样，不做修改**。
- 若未来 `scripts/check-references.sh` 的 `v1 keep set` 发生变化（比如真的 vendor 了 `benchmark`/`quality-gate`/`git-workflow` 对应的 ECC 组件），需要重新核实这份清单是否仍然成立。
- 本文档与 `docs/LOCAL-PATCHES.md` 的"未处理的 dangling refs（接受现状）"章节是同一批工作的两个产物：`LOCAL-PATCHES.md` 记录 2026-07-14 这轮做了哪些修改，本文档记录为什么剩下的不用改。
