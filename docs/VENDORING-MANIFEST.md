# Vendoring Manifest

> v1 候选从 ecc plugin 一次性复制到本 repo 的清单。一次落地后由 `scripts/vendor-from-ecc.sh` 维护，重跑 idempotent。post-v1 本地原创项单独记录，不改变 v1 基线含义。
>
> **基线**：ecc plugin `2.0.0-rc.1`（marketplace 路径 `~/.claude/plugins/marketplaces/ecc/`）
> **生成日期**：2026-05-16
> **Review 状态**：用户已 review 6/6 项（见文末），数字按最终决议）

## 概览

| 类型 | v1 keep total | from ecc | fork | 原创 (local/) |
|---|---|---|---|---|
| agents | 31 | **31** | 0 | 0 |
| skills | 73 | **73** | 0 | 0 |
| commands | 31 | **29** | 1 | 1 |
| **总计** | **135** | **133** | **1** | **1** |

> **事实更正（2026-05-16 vendor 阶段核实）**：`plan-orchestrate` 在 ecc 里实际是 **skill**（位于 `skills/plan-orchestrate/`），ecc commands 里本来就没有这个文件。因此「from ecc 28（排除 ecc 的 plan-orchestrate）」的算式有误 — v1 keep 29 commands 全部存在于 ecc commands 目录。ecc 那份 plan-orchestrate skill **依然不 vendor**（用户决定 fork user-level command 版到本 repo）。

> 不进本 repo 的两项（用户决定）：
> - `claude-api` (skill) — Claude Code 内置（anthropic-builtin），处理同 gstack，**官方维护，本 repo 完全不提**。从 SELECTION-v1.md 的 Python/AI 节删除。
> - 无其他「外部 vendor」项（v1 阶段）。

「特殊处理」两项：

- `plan-orchestrate` (command) — **fork user-level 版** (`~/.claude/commands/plan-orchestrate.md`) 到本 repo `commands/plan-orchestrate.md`，按 bare 架构改写。ecc 版（输出 `/orchestrate` 调用块）不 vendor。install.sh 时先 `.bak.<ts>` user-level 默认再覆盖。
- `ralph-init` (command + 子目录树) — **用户原创工具**，vendor 到 `commands/local/ralph-init.md` + `commands/local/ralph-init/`（30 文件、~144KB，含 references/、scripts/、scripts/fixtures/{valid,invalid}/）。install.sh 用 symlink 还原硬编码路径 `~/.claude/commands/ralph-init/`。

Post-v1 本地原创项：

- `video-extract` (skill) — **本地原创 skill**，源 `~/.claude/skills/video-extract/`，纳入本 repo `skills/video-extract/`。用途：视频内容抽取、字幕/转写、YouTube 403 / SABR / PO-token 时的真实浏览器播放、跳帧截图与音频兜底。它不是 ecc vendor 项，不写 `Source: ecc...` 注释。

## 归类修正（v1 selection 阶段错误）

| 项 | 误归 | 实际 |
|---|---|---|
| `skill-comply` | commands | **skill** |
| `skill-scout` | commands | **skill** |
| `skill-stocktake` | commands | **skill** |
| `hookify-rules` | 双重计入（skills 通用工作流组 + commands hookify 组） | **skill**（去掉 commands 那份） |

`SELECTION-v1.md` 等 install.sh 落地后同步修正。

## 来源 → 目标路径

```
SOURCE: ~/.claude/plugins/marketplaces/ecc/{agents,skills,commands}/
TARGET: ./agents/, ./skills/, ./commands/

agents:   ecc/agents/<name>.md       → agents/<name>.md           (单 .md 复制)
skills:   ecc/skills/<name>/         → skills/<name>/             (整目录复制，含 SKILL.md + references/* 等)
commands: ecc/commands/<name>.md     → commands/<name>.md         (单 .md 复制)
```

ecc 的 skill 一致结构（已 verify 多个样本）：`skills/<name>/SKILL.md` + 可选子目录（如 `references/`、`hooks/` 等）。整目录复制保留全部子文件。

## Agents（31，全部来自 ecc）

```
a11y-architect              code-explorer              docs-lookup
build-error-resolver        code-reviewer              fastapi-reviewer
code-architect              code-simplifier            harness-optimizer
comment-analyzer            database-reviewer          loop-operator
django-build-resolver       doc-updater                mle-reviewer
django-reviewer             performance-optimizer      planner
pr-test-analyzer            python-reviewer            pytorch-build-resolver
refactor-cleaner            rust-build-resolver        rust-reviewer
security-reviewer           silent-failure-hunter      swift-build-resolver
swift-reviewer              tdd-guide                  type-design-analyzer
typescript-reviewer
```

## Skills（73 from ecc，分组对应 SELECTION-v1.md）

**TS / 前端（18）**

```
accessibility           bun-runtime              design-system
frontend-design-direction frontend-patterns       frontend-slides
liquid-glass-design     make-interfaces-feel-better
motion-advanced         motion-foundations       motion-patterns
motion-ui               nestjs-patterns          nextjs-turbopack
nuxt4-patterns          ui-demo                  ui-to-vue
vite-patterns
```

**Python / AI（14 from ecc）**

```
django-celery       django-patterns       django-security
django-tdd          django-verification   fal-ai-media
fastapi-patterns    mle-workflow          prompt-optimizer
python-patterns     python-testing        pytorch-patterns
remotion-video-creation  videodb
```

注：`claude-api` 是 Claude Code 内置 skill（官方维护），SELECTION-v1.md 不列、本 repo 完全不提。

**Agent 工程（15 from ecc）**

```
agent-architecture-audit       agent-eval
agent-harness-construction     agent-introspection-debugging
agentic-engineering            agentic-os
ai-regression-testing          autonomous-agent-harness
autonomous-loops               continuous-agent-loop
continuous-learning            continuous-learning-v2
eval-harness                   ralphinho-rfc-pipeline
verification-loop
```

注：`ralph-init` 是用户原创 command（非 skill），按 commands 节处理，vendor 到 `commands/local/`。SELECTION-v1.md 应将其从「Agent 工程 skills」组移到 commands 节。

**通用工作流（23 from ecc — 含原属 commands 的 hookify-rules）**

```
api-design                       architecture-decision-records
canary-watch                     clickhouse-io
codebase-onboarding              coding-standards
database-migrations              deployment-patterns
docker-patterns                  documentation-lookup
error-handling                   gateguard
hexagonal-architecture           hookify-rules
plankton-code-quality            postgres-patterns
redis-patterns                   repo-scan
safety-guard                     security-bounty-hunter
security-review                  security-scan
strategic-compact
```

**归类修正（3，从 commands 移到 skills）**

```
skill-comply    skill-scout    skill-stocktake
```

## Post-v1 本地原创 Skills（1）

```
video-extract       → 源 ~/.claude/skills/video-extract/
                    → 目标 skills/video-extract/
                    → 10 文件，含 SKILL.md、reference/gotchas.md、scripts/{7 sh + 1 js}
```

## Commands（29 from ecc + 1 fork + 1 原创 = 31）

**from ecc (29)** —— 全部 v1 keep commands 都在 ecc `commands/` 目录里（ecc 的 plan-orchestrate 实际是 skill，不在此列）：

```
build-fix           code-review        cost-report
ecc-guide           fastapi-review     harness-audit
hookify             hookify-configure  hookify-help
hookify-list        learn              learn-eval
loop-start          loop-status        model-route
plan                plan-prd           prune
python-review       refactor-clean     rust-build
rust-review         rust-test          security-scan
skill-create        skill-health       test-coverage
update-codemaps     update-docs
```

**fork from user-level (1)** —— ecc 版输出 `/orchestrate` 调用块，user-level 版输出 Agent tool 调用块且更贴合 bare 架构，因此 fork 后者：

```
plan-orchestrate    → 源 ~/.claude/commands/plan-orchestrate.md
                    → 目标 commands/plan-orchestrate.md
                    → 按 bare 架构改写（详见 README 附 A-H 改动清单）
```

**原创 from user-level (1)** —— 用户原创工具，vendor 整个子系统进版本控制：

```
ralph-init          → 源 ~/.claude/commands/ralph-init.md + ~/.claude/commands/ralph-init/
                    → 目标 commands/local/ralph-init.md + commands/local/ralph-init/
                    → 30 文件、~144KB，含 references/{4 md} + scripts/{3 .py + 1 .sh}
                                + scripts/fixtures/{valid/3 + invalid/18}
```

## 最终数字

v1 基线：

| 类型 | from ecc | fork | 原创 | total |
|---|---|---|---|---|
| agents | 31 | 0 | 0 | 31 |
| skills | 73 | 0 | 0 | 73 |
| commands | 29 | 1 | 1 | 31 |
| **总** | **133** | **1** | **1** | **135** |

当前 repo 额外 post-v1 本地项：

| 类型 | 本地原创新增 | 当前 total |
|---|---:|---:|
| skills | 1 (`video-extract`) | 74 |
| commands | 0 | 31 |

> v1 keep total **135** 项（与 prior summary 一致；取代 SELECTION-v1.md 原写的 ~137）。差异来源：
> - 归类修正 -0（skill-comply/scout/stocktake 从 commands 移到 skills，相互抵消）
> - claude-api 删除 -1（不算 SOURCES 登记）
> - hookify-rules 去重 -1（原双重计入，现仅 skills 算一次）
> - ralph-init 重新归类（原算 skills，实际是 command）-0
> - plan-orchestrate ecc 真实归类是 skill 不是 command，但 v1 keep 不包含它（fork user-level command 版） -0
>
> SELECTION-v1.md 已同步更新。

## 文件头标注

每个 vendored 文件**头部**插入注释（保留原文件内容不动）：

```
<!-- Source: ecc@2.0.0-rc.1, vendored on 2026-05-16 from <ecc-relative-path> -->
```

- **agent / command**（`.md`）— 在第一行 frontmatter 之前插，或在 frontmatter 之后第一段插（取决于 markdown 解析器对头部 HTML 注释的容错）
- **skill**（目录）— 仅在 `<skill-name>/SKILL.md` 头部插，其他子文件（references/、scripts/ 等）不动

具体插入策略 vendor 脚本里实现。

## Vendor 脚本设计

文件：`scripts/vendor-from-ecc.sh`

```
功能：
  - 读取 ECC_ROOT 环境变量（默认 ~/.claude/plugins/marketplaces/ecc）
  - 读取 ECC_VERSION（从 $ECC_ROOT/VERSION 文件）
  - 读取 DATE（默认 today）
  - 读取 manifest（agents/skills/commands 三个 keep 名单 — 硬编码或从 SELECTION-v1.md 解析）
  - 对每项：
      - 检查目标是否已存在 → --force 才覆盖
      - 复制 ecc 源 → repo 目标
      - 头部插 Source 注释
  - 默认 dry-run；--apply 真复制；--force 跳过已存在检查

输入：
  - $ECC_ROOT (env, optional)
  - $DATE     (env, optional)
  - --apply / --force / --dry-run (flags)

输出：
  - 每项一行 status：✓ copied / ⊙ skipped (exists) / ✗ source missing
  - 完成后总数报告
```

待 manifest review 完后写。

## Dangling Reference 扫描

文件：`scripts/check-references.sh`

- 对每个 vendored 文件，grep 引用模式：
  - `ecc:<name>` / `subagent_type=.*<name>` / `from skill <name>` / 等
- 如果引用的 name 不在 v1 keep 集合 → **flag dangling**
- 处理：
  - 补 keep 那个 name（加入 v1 keep）
  - 改引用（指到 v1 keep 里的替代品）
  - 注释掉引用（如非必要）

跑时机：vendor 完成后、install.sh 之前。

## Review 决议（2026-05-16 用户确认）

- [x] 三大清单（31 agents + 73 skills + 28 commands from ecc）整体 OK，推进
- [x] 文件头标注格式 → **HTML 注释**（`<!-- Source: ecc@2.0.0-rc.1, vendored on 2026-05-16 from <path> -->`，插入文件顶部）
- [x] 归类修正 3 项（skill-comply/scout/stocktake）按 ecc 实际归类，从 commands 移到 skills；hookify-rules 去 commands 重复，仅 skills 算一次 — **同意**
- [x] `plan-orchestrate` from ecc 不 vendor，fork user-level 那份按 bare 架构改写 — **同意**
- [x] `claude-api` — **不进 repo、不进 SOURCES.md**（Claude Code 内置 skill，处理同 gstack，由官方维护）。SELECTION-v1.md 的 claude-api 条目删除
- [x] `ralph-init` — **用户原创工具，vendor 到 `commands/local/`**（不是 install.sh 跳过！原 prior summary 默认错误）。SELECTION-v1.md 中 ralph-init 从 Agent 工程 skills 组移到 commands 节

下一步：
1. 写 `scripts/vendor-from-ecc.sh`（--dry-run / --apply / --force）
2. 跑 dry-run → 用户 review → --apply
3. 同步更新 SELECTION-v1.md（数字 137 → 134，结构调整 4 处）
4. 写 `scripts/check-references.sh`
5. Fork plan-orchestrate.md（按 prior summary 列的 A-H 改动清单）
6. 写 install.sh
7. 第一次 install（与 ecc plugin 共存验证）
