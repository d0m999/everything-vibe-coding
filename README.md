# everything-vibe-coding

个人精简版的 Claude Code 配置。从 [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)（下文简称 **ecc**）出发，按「能用上的才进来」原则裁剪；其他来源的 skill / agent 也欢迎引入。

## 为什么有这个 repo

ecc 太全 — 500+ skills、几十个 agent、覆盖几十种技术栈。对我而言：

- 上下文被 schema/描述撑爆，影响主任务的注意力预算
- 选择太多反而记不住、不会用
- 绝大多数项服务于我不碰的技术栈（Rust/Quarkus/HarmonyOS/…）

所以这个 repo 维护一份「**白名单 + 个人补丁 + 选择性引入的外部 skill**」，作为我 `~/.claude/` 的唯一来源。

## 维护原则

按优先级：

1. **少而精**。每加一项要答得出「上次什么时候用过」「下个月会用吗」。答不出的不加。
2. **完全自主**。不与上游建立 `git remote upstream` 关系，避免被上游节奏推着走。
3. **可追溯**。vendor 进来的文件能说清来自哪个 repo、哪个 commit、哪天抓的。
4. **本地优先**。本地补丁的优先级高于上游版本；上游同步不静默覆盖本地修改。
5. **可裁汰**。长时间没用上的从主目录降级到 `attic/`，再没起色就删。

## 仓库结构

```
.
├── README.md
├── install.sh                # 逐项 symlink 到 ~/.claude/
├── skills/                   # 启用的 skills（含 local/ 子目录放原创）
├── agents/                   # 启用的 agents
├── commands/                 # 启用的 commands
├── hooks/                    # 启用的 hooks
├── rules/                    # rules/ 配置
├── settings/                 # settings.json 片段(可选)
├── attic/                    # 下架但留底（不参与 install）
├── docs/
│   ├── SELECTION-v1.md       # v1 白名单及评分（问卷产出）
│   ├── UPSTREAM.md           # 上游变更评估日志
│   ├── SOURCES.md            # 多来源追踪（ecc + 其他 repo）
│   └── LOCAL-PATCHES.md      # 对 vendored 内容的本地修改清单
└── CHANGELOG.md
```

## 安装

```bash
./install.sh              # 把 skills/agents/... 逐项 symlink 到 ~/.claude/
./install.sh --dry-run    # 看一下会做什么但不执行
./install.sh --backup     # 安装前把 ~/.claude/ 备份到 ~/.claude.bak-<ts>/
```

Codex 安装 skills，并把 commands 生成成 Codex skill wrappers：

```bash
./install-codex.sh          # dry-run，预览写入 ~/.codex/skills/ 的内容
./install-codex.sh --apply  # 逐项 symlink skills，并生成/链接 command wrappers
```

Codex 的 `$` skill picker 会显示 command 名，例如 `commands/code-review.md` 对应 `$code-review`，`commands/local/ralph-init.md` 对应 `$ralph-init`。`~/.codex/prompts` 也会保留一份兼容链接，但它不是主要入口。

设计要点：

- **逐项 symlink**（不是整个目录 symlink）。这样 `~/.claude/skills/` 下既可以放本 repo 管理的 skill，也容得下临时、未纳入 repo 的内容。
- **Codex 也逐项 symlink** 到 `$CODEX_HOME/skills`（默认 `~/.codex/skills`），并为 `commands/*.md` 生成 `.agents/skills/evc-command-*` wrapper 后链接进去，避免覆盖 Codex 自带的 `.system` skills 和其他本地安装项。
- **同名冲突给提示、不静默覆盖**。已存在的目标会列出来，需要 `--force` 才覆盖。
- **`attic/` 不参与 install**。

## v1 筛选方法

### 三个评估维度

| 维度 | 高分含义 |
|------|----------|
| **使用频率** | 几乎每周会用到 |
| **上手成本** | 看到名字就知道干啥、不用读说明 |
| **专属价值** | Claude 自己干不了，必须这个 skill 才做得好 |

三项都不高 → **不要**。至少一项明显高 → **保留**。模糊地带 → **观察（attic/）**。

### 三类去留

- **保留（keep）**：进主目录，参与 install。
- **观察（observe）**：进 `attic/`，install 时跳过。每季度复评一次是升回主目录还是删除。
- **不要（drop）**：不进 repo。在 `docs/UPSTREAM.md` 里留一句 reject 原因，避免下次重复评估。

### v1 问卷流程（在 Claude Code 会话中分批进行）

v1 白名单不是一次性凭印象列出来，而是分阶段问答生成：

1. **场景定锚**：先列出我在 Claude Code 里实际做的 5-10 件事（写代码、review、QA、规划、文档…），作为打分的语境。
2. **按场景过候选**：每个场景下相关的上游项一批一批用 `AskUserQuestion` 表决「保留 / 观察 / 不要」，每批不超过 4 项。
3. **横向去重**：同一类功能（code review、QA、planning…）的多个 skill，强制收敛到 1-2 个。
4. **空白补足**：上游没覆盖的场景登记到 `docs/SOURCES.md`，作为「外部引入候选」。
5. **冷启动期**：v1 落地后跑 2-4 周，期间记录哪些用上了、哪些一次没碰，再做一次缩编。

每一轮的产出累积写入 `docs/SELECTION-v1.md`。

## 更新模型（v1 落地之后）

### 上游 ecc 有变化

不自动 `git pull`。流程：

1. 浏览 ecc 的 commit / release diff（手动，或让 Claude Code 帮看）。
2. 对每条变更回答两个问题：「影响到我保留的项了吗？」「新增的项里有我会用的吗？」
3. **影响保留项** → 评估是否同步（注意冲突 `docs/LOCAL-PATCHES.md` 里的本地补丁）。**新增项** → 走 v1 问卷的三类去留流程。
4. 在 `docs/UPSTREAM.md` 追加一行：日期、上游 commit、决定（synced / observed / rejected）、一句原因。

### 引入外部 repo（非 ecc）

1. 在 `docs/SOURCES.md` 登记：来源 repo URL、commit hash、抓取日期、抓取的文件清单。
2. 文件头加注释：`# Source: <repo>@<commit>, vendored on <date>`
3. 如有改动，进入 `docs/LOCAL-PATCHES.md`。

### 我自己写的（原创）

放进对应分类的 `local/` 子目录（`skills/local/` 等），与 vendored 内容隔开。原创内容不需要 SOURCES 记录，但要在 `CHANGELOG.md` 提一句。

### 本地补丁（对 vendored 内容的修改）

- 文件头加注释：`# Local patch: <one-line reason>`
- 在 `docs/LOCAL-PATCHES.md` 列一行：文件路径、修改概要、原因
- 目的：将来从上游同步新版本时能识别出需要 re-apply 的地方

## 季度回顾

每 3 个月一次，跑这套：

1. **使用统计**：过去一季度哪些项一次没被触发？（从 Claude Code 的 session 记录粗估）
2. **降级**：未用项进 `attic/`。
3. **裁汰**：上次回顾就已在 `attic/` 的 → 删除（在 CHANGELOG 留一行）。
4. **外部扫描**：看一眼 awesome-claude-code 类列表或社区，有没有值得引入的新东西。
5. **重评分**：保留项重新过三维度，分数下降明显的也考虑下架。

## Git 工作流

个人 repo，main 直推。每次变更在 `CHANGELOG.md` 顶部加一行：

```
YYYY-MM-DD  add|drop|patch|sync  <path>  <一句话说明>
```

例：

```
2026-05-16  add   skills/investigate          冷启动调试场景必备
2026-05-17  drop  skills/ecc:harmonyos-app-resolver   不写 HarmonyOS
2026-05-20  sync  agents/code-reviewer        upstream ecc@abc123
2026-05-22  patch hooks/auto-format.sh        改用本地 prettier 配置
```

## 当前状态

- [x] v1 问卷完成 → `docs/SELECTION-v1.md`（keep **135 项** / drop ~360+ 项，agents 31 / skills 73 / commands 31 = 29 from ecc + 1 fork + 1 原创）
- [x] vendoring manifest review 完成 → `docs/VENDORING-MANIFEST.md`（2026-05-16 用户确认 6/6 项）
- [x] `scripts/vendor-from-ecc.sh` 完成
- [x] `scripts/check-references.sh` 完成（识别 74 个 drop name 提及，按 count≥2+1:1替代品 筛选 fix 了 6 处 `architect`/`e2e-runner`，其余在 `docs/LOCAL-PATCHES.md` 留底）
- [x] `commands/plan-orchestrate.md` fork 完成（按附 A-H 改动清单）
- [x] `install.sh` 完成
- [x] 上游基线 ecc commit：`f04702b` (`2.0.0-rc.1`，2026-05-16 抓取)
- [x] 首次 install 完成 + 共存验证（与 ecc plugin 共存，bare 名字 + ecc:&lt;name&gt; 双 namespace 并存）
- [x] 冷启动期开始日期：**2026-05-16**（4 周后即 2026-06-13 做第一次缩编评估）

## 附 A-H：plan-orchestrate fork 改动清单

> 来源：`~/.claude/commands/plan-orchestrate.md`（user-level，328 行）
> 目标：`commands/plan-orchestrate.md`

- **A**. 删 Phase 0 step 2 整段（ECC_MODE 检测）— bare 架构永远输出 bare 名字无前缀。
- **B**. Phase 0 step 4 扩展为 `py_sub ∈ {mle, django, fastapi, generic}`，决定 reviewer + build resolver：
  - mle: deps 含 torch OR plan 词（pytorch / training / dataloader / fine-tune / lora）→ `mle-reviewer` + `pytorch-build-resolver`
  - django: `manage.py` + django deps OR plan 词（django / DRF / celery / orm migration）→ `django-reviewer` + `django-build-resolver`
  - fastapi: fastapi deps OR plan 词（fastapi / pydantic / asgi）→ `fastapi-reviewer` + `build-error-resolver`
  - generic: → `python-reviewer` + `build-error-resolver`
- **C**. Catalogue 节（user-level 57-80 行）替换：
  - 删：`architect` / `e2e-runner` / `chief-of-staff` / `cpp-*` / `go-*` / `java-*` / `kotlin-*` / `flutter-*`
  - 加：`code-architect` / `code-explorer` / `silent-failure-hunter` / `swift-reviewer` / `swift-build-resolver` / `django-reviewer` / `django-build-resolver` / `fastapi-reviewer` / `mle-reviewer`
- **D**. Phase 2 tag→chain 表：
  - `design`: `code-explorer,planner,code-architect`
  - `refactor`: `code-architect,refactor-cleaner,<lang>-reviewer`
  - `migration`: `code-explorer,code-architect,tdd-guide,<lang>-reviewer`
  - `test`: `tdd-guide,<lang>-reviewer`（删 e2e-runner，rationale 注明 e2e 接 gstack `/qa`）
  - 新增 `debug`: `silent-failure-hunter,<lang>-reviewer`（触发词：error swallow / fallback / silently / handle / lost error）
- **E**. Phase 2 chain composition rules 5/6 扩展 `<lang>-reviewer` 和 `<lang>-build-resolver` 解析（含 py_sub 4 分支 + swift + rust + typescript + unknown→`code-reviewer` / `build-error-resolver`）。
- **F**. Examples 简化为 1 个（推荐 Swift impl + db 例子，演示 `swift-reviewer` + `database-reviewer` chain），删 plugin/legacy 对比例子。
- **G**. Notes 加：「test chain 仅覆盖单元/集成评审；E2E 步骤接 gstack `/qa` / `/browse` / `/design-review`」。
- **H**. Phase 5 self-check 删去与 plugin/legacy 形式相关的检查项。
