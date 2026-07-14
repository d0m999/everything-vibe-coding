# v1 Selection

> v1 白名单 + drop 清单 + 多入口默认路径。来源：2026-05-16 与 Claude Code 进行的 7 轮结构化问卷。

## 画像（打分语境）

- **工作环节**：写代码 / 调试 / review / 规划，全覆盖、无明显偏废
- **技术栈**：
  - TS/JS：React + Next.js、Vue + Nuxt、Node 后端（Express / NestJS / Bun）
  - Python：Django（含 DRF/Celery）、FastAPI、AI/ML（PyTorch / LangChain / Claude SDK）
  - Swift：iOS / macOS
  - Rust：cargo / wasm
- **gstack 锚点**（已在用、离不开的）：
  - QA / 浏览器自动化：`/qa`、`/browse`、`/design-review`
  - 规划 / 设计：`/plan-*`、`/office-hours`、`/design-consultation`
  - 调试 / 安全约束：`/investigate`、`/codex`、`/careful`、`/freeze`
- **明确缺位**：`/ship`、`/review`、`/retro` 未被列为「离不开」 → PR / 发布流主走 gstack `/ship`，但**不是高频依赖**

## v1 多入口默认路径

按场景自然分流，不强制单一默认。各入口职责分工：

| 场景 | gstack | ecc agent | ecc command | ecc skill |
|------|--------|-----------|-------------|-----------|
| Plan / 规划 / 拆解 | `/plan-eng-review`、`/office-hours` | `planner`、`code-architect` | `plan`、`plan-prd`、`plan-orchestrate` | `agent-architecture-audit` |
| 写完代码 review | `/codex review` | `code-reviewer` + 语言专用 reviewer | `code-review` + 语言专用 | — |
| PR / Ship | `/ship`（独家） | — | — | — |
| QA / E2E | `/qa`、`/browse`、`/design-review`（独家） | — | — | — |
| Debug 根因 | `/investigate` | `silent-failure-hunter` | — | — |
| 重构 / 清理 | — | `refactor-cleaner`、`code-simplifier` | `refactor-clean` | — |
| Build 错误 | — | `build-error-resolver` + 语言专用 | `build-fix` | — |
| 文档 / Codemap | `/document-release` | `doc-updater` | `update-codemaps`、`update-docs` | `documentation-lookup` |
| 安全 | `/cso` | `security-reviewer` | `security-scan` | `security-review`、`security-bounty-hunter` |
| Loop / autonomous | — | `loop-operator`、`harness-optimizer` | `loop-start`、`loop-status`、`harness-audit` | `ralph-init`、`continuous-agent-loop`、`verification-loop` |

## Keep 名单

### Agents（31）

**实现 / 规划 / 重构（8）**

- `ecc:planner`
- `ecc:code-architect`
- `ecc:code-explorer`
- `ecc:tdd-guide`
- `ecc:refactor-cleaner`
- `ecc:code-simplifier`
- `ecc:comment-analyzer`
- `ecc:type-design-analyzer`

**通用 review（4）**

- `ecc:code-reviewer`
- `ecc:security-reviewer`
- `ecc:database-reviewer`
- `ecc:pr-test-analyzer`

**特殊视角（4）**

- `ecc:silent-failure-hunter`
- `ecc:performance-optimizer`
- `ecc:a11y-architect`
- `ecc:build-error-resolver`

**框架专用（3）**

- `ecc:fastapi-reviewer`
- `ecc:mle-reviewer`
- `ecc:pytorch-build-resolver`
- ~~`ecc:django-reviewer`~~ — 2026-07-14 归档到 `attic/agents/`，见下方「已归档」
- ~~`ecc:django-build-resolver`~~ — 同上

**语言专用（4）**

- `ecc:typescript-reviewer`
- `ecc:python-reviewer`
- `ecc:swift-reviewer`
- `ecc:swift-build-resolver`
- ~~`ecc:rust-reviewer`~~ — 2026-07-14 归档到 `attic/agents/`，见下方「已归档」
- ~~`ecc:rust-build-resolver`~~ — 同上

### 已归档（2026-07-14，v1 选型之后）

以下条目当初选入 v1 keep，随后归档到 `attic/`，**不再 vendor、不得在 agent 目录中引用**：

| 组件 | 归档位置 | 原因 |
|---|---|---|
| `django-reviewer` / `django-build-resolver` | `attic/agents/` | Django 不在实际技术栈内；`py_sub=django` 分支已从 `plan-orchestrate` 移除 |
| `rust-reviewer` / `rust-build-resolver` | `attic/agents/` | 同上，Rust 出 v1 范围 |
| `rust-build` / `rust-review` / `rust-test` | `attic/commands/` | 随 rust agent 一并归档 |
| django 系 5 个 skill、前端 motion/vite/nuxt 系等共 22 个 skill | `attic/skills/` | 见 `docs/LOCAL-PATCHES.md` |

`scripts/vendor-from-ecc.sh` 现在会拒绝 vendor 任何存在于 `attic/` 的名字（`⊘ ARCHIVED`，exit 3），
所以这份名单不会被下一次 `--apply` 悄悄复活。

**工具 / 流程（2）**

- `ecc:loop-operator`
- `ecc:harness-optimizer`

**文档 / 帮助（2）**

- `ecc:doc-updater`
- `ecc:docs-lookup`

### Skills（73）

**TS / 前端（18）**

- 框架补丁：`ecc:nextjs-turbopack`、`ecc:vite-patterns`、`ecc:nuxt4-patterns`、`ecc:bun-runtime`、`ecc:nestjs-patterns`
- 动画 / 设计实现：`ecc:motion-foundations`、`ecc:motion-patterns`、`ecc:motion-ui`、`ecc:motion-advanced`、`ecc:liquid-glass-design`、`ecc:frontend-design-direction`
- UI / 设计系统：`ecc:design-system`、`ecc:ui-demo`、`ecc:ui-to-vue`、`ecc:accessibility`、`ecc:frontend-patterns`、`ecc:frontend-slides`、`ecc:make-interfaces-feel-better`

**Python / AI（14）**

- 通用 Python：`ecc:python-patterns`、`ecc:python-testing`
- Django：`ecc:django-patterns`、`ecc:django-celery`、`ecc:django-tdd`、`ecc:django-security`、`ecc:django-verification`
- FastAPI：`ecc:fastapi-patterns`
- AI / ML：`ecc:pytorch-patterns`、`ecc:mle-workflow`、`ecc:prompt-optimizer`、`ecc:fal-ai-media`、`ecc:videodb`、`ecc:remotion-video-creation`

注：`claude-api` 是 Claude Code 内置 skill（官方维护，同 gstack 处理方式），本 repo 完全不提（不 vendor、不登记 SOURCES.md）。

**Agent 工程（15）**

- 架构与调试：`ecc:agent-architecture-audit`、`ecc:agent-introspection-debugging`、`ecc:agent-harness-construction`、`ecc:autonomous-agent-harness`、`ecc:autonomous-loops`、`ecc:agentic-engineering`、`ecc:agentic-os`
- Eval / 持续学习：`ecc:eval-harness`、`ecc:continuous-learning`、`ecc:continuous-learning-v2`、`ecc:ai-regression-testing`、`ecc:agent-eval`
- Loop / 流水线：`ecc:ralphinho-rfc-pipeline`、`ecc:continuous-agent-loop`、`ecc:verification-loop`

注：`ralph-init` 是用户原创 command（非 skill），见 Commands 节「原创工具」组。

**通用工作流（23）**

- 质量 / 架构原则：`ecc:coding-standards`、`ecc:plankton-code-quality`、`ecc:error-handling`、`ecc:architecture-decision-records`、`ecc:hexagonal-architecture`、`ecc:api-design`
- 数据库 / 部署 / 运维：`ecc:database-migrations`、`ecc:postgres-patterns`、`ecc:redis-patterns`、`ecc:clickhouse-io`、`ecc:deployment-patterns`、`ecc:docker-patterns`、`ecc:canary-watch`
- 安全 / 调试：`ecc:security-scan`、`ecc:security-review`、`ecc:security-bounty-hunter`、`ecc:gateguard`、`ecc:safety-guard`、`ecc:hookify-rules`、`ecc:documentation-lookup`、`ecc:codebase-onboarding`、`ecc:repo-scan`、`ecc:strategic-compact`

**Skill 维护工具（3）** — 归类修正：ecc 里实际是 skill，从原 commands 节移过来

- `ecc:skill-comply`、`ecc:skill-scout`、`ecc:skill-stocktake`

### Post-v1 本地原创 Skills（1）

- `video-extract`（本地原创，纳入 `skills/video-extract/`；用于读取/总结/转写视频，快路径走字幕或 `yt-dlp`，YouTube 403 / SABR / PO-token 时走真实浏览器播放、跳帧截图与音频兜底）

### Commands（31）

> 29 from ecc + 1 fork (`plan-orchestrate`) + 1 原创 (`ralph-init`)
>
> 注：`plan-orchestrate` 在 ecc 里实际是 skill（`skills/plan-orchestrate/`），ecc commands 目录没有此项；fork 来源是 user-level `~/.claude/commands/plan-orchestrate.md`（command 形式，输出 Agent tool 调用块）。

**语言 / 框架（5）**

- `ecc:python-review`
- `ecc:rust-review`、`ecc:rust-build`、`ecc:rust-test`
- `ecc:fastapi-review`

**通用 review / build / test（5）**

- `ecc:code-review`
- `ecc:test-coverage`
- `ecc:build-fix`
- `ecc:refactor-clean`
- `ecc:security-scan`

**计划 / 文档（5）**

- `ecc:plan`、`ecc:plan-prd`
- `plan-orchestrate`（**fork** user-level，按 bare 架构改写，非 ecc 版）
- `ecc:update-codemaps`、`ecc:update-docs`

**Loop / 成本 / 元能力（8）**

- `ecc:loop-start`、`ecc:loop-status`、`ecc:harness-audit`
- `ecc:cost-report`、`ecc:model-route`、`ecc:prune`
- `ecc:learn`、`ecc:learn-eval`

**Skill / Hook 维护（7）** — 归类修正后

- Skill 工具：`ecc:skill-create`、`ecc:skill-health`、`ecc:ecc-guide`
- Hookify：`ecc:hookify`、`ecc:hookify-help`、`ecc:hookify-list`、`ecc:hookify-configure`

注：原列在此节的 `skill-comply / skill-scout / skill-stocktake`（实际是 skills）已移到 Skills 节「Skill 维护工具」组；`hookify-rules`（实际是 skill）原双重计入，去 commands 重复，仅 Skills 节「通用工作流」算一次。

**原创工具（1）**

- `ralph-init`（vendor 到 `commands/local/ralph-init.md` + `commands/local/ralph-init/`，30 文件/~144KB，含 references/、scripts/、scripts/fixtures/{valid,invalid}/）

### Hooks

**不预装**。需要时通过 `ecc:hookify` 命令从 transcript 中识别可 hook 化的行为，按需生成本地 hooks。

### Settings

**不预装**。本地 `~/.claude/settings.json` 自行管理。

## Drop（不进 repo — 已评估、不需重评）

### 语言不匹配

- **Go**：`ecc:go-reviewer`、`ecc:go-build-resolver`、`ecc:go-review`、`ecc:go-build`、`ecc:go-test`、`ecc:golang-patterns`、`ecc:golang-testing`
- **Kotlin / Android**：`ecc:kotlin-reviewer`、`ecc:kotlin-build-resolver`、`ecc:kotlin-review`、`ecc:kotlin-build`、`ecc:kotlin-test`、`ecc:kotlin-patterns`、`ecc:kotlin-coroutines-flows`、`ecc:kotlin-exposed-patterns`、`ecc:kotlin-ktor-patterns`、`ecc:kotlin-testing`、`ecc:android-clean-architecture`、`ecc:compose-multiplatform-patterns`
- **C++**：`ecc:cpp-reviewer`、`ecc:cpp-build-resolver`、`ecc:cpp-review`、`ecc:cpp-build`、`ecc:cpp-test`、`ecc:cpp-coding-standards`、`ecc:cpp-testing`
- **Java / Spring / Quarkus**：`ecc:java-reviewer`、`ecc:java-build-resolver`、`ecc:java-coding-standards`、`ecc:jpa-patterns`、`ecc:springboot-patterns`、`ecc:springboot-security`、`ecc:springboot-tdd`、`ecc:springboot-verification`、`ecc:quarkus-patterns`、`ecc:quarkus-security`、`ecc:quarkus-tdd`、`ecc:quarkus-verification`、`ecc:gradle-build`
- **C# / .NET**：`ecc:csharp-reviewer`、`ecc:csharp-testing`、`ecc:dotnet-patterns`
- **F#**：`ecc:fsharp-reviewer`、`ecc:fsharp-testing`
- **Dart / Flutter**：`ecc:dart-build-resolver`、`ecc:flutter-reviewer`、`ecc:flutter-build`、`ecc:flutter-test`、`ecc:flutter-review`、`ecc:flutter-dart-code-review`、`ecc:dart-flutter-patterns`
- **HarmonyOS**：`ecc:harmonyos-app-resolver`
- **Perl**：`ecc:perl-patterns`、`ecc:perl-security`、`ecc:perl-testing`
- **其他**：`ecc:laravel-patterns`、`ecc:laravel-tdd`、`ecc:laravel-security`、`ecc:laravel-verification`、`ecc:laravel-plugin-discovery`、`ecc:tinystruct-patterns`、`ecc:mysql-patterns`、`ecc:prisma-patterns`、`ecc:angular-developer`、`ecc:nodejs-keccak256`

### 特殊行业 / 领域

- 医疗：`ecc:healthcare-reviewer`、`ecc:healthcare-cdss-patterns`、`ecc:healthcare-emr-patterns`、`ecc:healthcare-eval-harness`、`ecc:healthcare-phi-compliance`、`ecc:hipaa-compliance`
- DeFi / 金融：`ecc:defi-amm-security`、`ecc:llm-trading-agent-security`、`ecc:evm-token-decimals`、`ecc:agent-payment-x402`
- 物流 / 贸易：`ecc:carrier-relationship-management`、`ecc:customs-trade-compliance`、`ecc:customer-billing-ops`、`ecc:finance-billing-ops`、`ecc:inventory-demand-planning`、`ecc:logistics-exception-management`、`ecc:returns-reverse-logistics`、`ecc:production-scheduling`、`ecc:quality-nonconformance`、`ecc:unified-notifications-ops`
- 投资人 / 市场：`ecc:investor-materials`、`ecc:investor-outreach`、`ecc:market-research`
- 科研：`ecc:scientific-pkg-gget`、`ecc:scientific-db-pubmed-database`、`ecc:scientific-db-uspto-database`、`ecc:scientific-thinking-scholar-evaluation`、`ecc:scientific-thinking-literature-review`
- 能源 / 食品 / 签证：`ecc:energy-procurement`、`ecc:nutrient-document-processing`、`ecc:visa-doc-translate`
- 视频：`ecc:manim-video`、`ecc:video-editing`（注意：`fal-ai-media`、`videodb`、`remotion-video-creation` 是创作工具已 keep）

### 网络 / 运维专题

- 网络：`ecc:network-architect`、`ecc:network-config-reviewer`、`ecc:network-troubleshooter`、`ecc:network-bgp-diagnostics`、`ecc:network-config-validation`、`ecc:network-interface-health`、`ecc:cisco-ios-patterns`、`ecc:netmiko-ssh-automation`
- Homelab：`ecc:homelab-architect`、`ecc:homelab-network-setup`、`ecc:homelab-network-readiness`、`ecc:homelab-pihole-dns`、`ecc:homelab-vlan-segmentation`、`ecc:homelab-wireguard-vpn`

### 非工作流工具

- 项目管理：`ecc:jira-integration`、`ecc:jira`
- 通信：`telegram:configure`、`telegram:access`、`ecc:x-api`、`ecc:messages-ops`、`ecc:email-ops`、`ecc:google-workspace-ops`
- 个人通信枢纽：`ecc:chief-of-staff`
- SEO：`ecc:seo-specialist`、`ecc:seo`
- 桌面 E2E：`ecc:windows-desktop-e2e`

### 与 gstack 重叠（横向去重决定）

- E2E / 浏览器自动化：`ecc:e2e-runner`（agent）、`ecc:browser-qa`、`ecc:e2e-testing`、`ecc:ai-regression-testing`（注：作为 skill 已 drop；作为 Eval 组 skill 重复出现的版本 keep）、`ecc:click-path-audit`、`ecc:workspace-surface-audit`
- PR / Git：`ecc:git-workflow`、`ecc:github-ops`、`ecc:pr`（command）、`ecc:review-pr`（command）；skill 版本的 `pr`、`review`
- 上下文 / 检索 / 成本（skill 重叠 command keep）：`ecc:context-budget`、`ecc:iterative-retrieval`、`ecc:search-first`、`ecc:token-budget-advisor`、`ecc:cost-tracking`、`ecc:cost-aware-llm-pipeline`

### 其他工具类 drop

- GAN：`ecc:gan-evaluator`、`ecc:gan-generator`、`ecc:gan-planner`、`ecc:gan-design`、`ecc:gan-build`、`ecc:gan-style-harness`
- Opensource：`ecc:opensource-forker`、`ecc:opensource-sanitizer`、`ecc:opensource-packager`、`ecc:opensource-pipeline`
- 帮助 / 元工具：`ecc:claude-code-guide`、`ecc:conversation-analyzer`
- 会话管理：`ecc:checkpoint`、`ecc:save-session`、`ecc:resume-session`、`ecc:sessions`
- PRP 流水线：`ecc:prp-prd`、`ecc:prp-plan`、`ecc:prp-implement`、`ecc:prp-commit`、`ecc:prp-pr`
- 项目初始化：`ecc:project-init`、`ecc:projects`、`ecc:feature-dev`
- 实验性：`ecc:aside`、`ecc:evolve`、`ecc:santa-loop`、`ecc:santa-method`、`ecc:promote`
- Multi-* 系列：`ecc:multi-backend`、`ecc:multi-frontend`、`ecc:multi-workflow`、`ecc:multi-plan`、`ecc:multi-execute`
- Instinct 系列：`ecc:instinct-export`、`ecc:instinct-import`、`ecc:instinct-status`
- 其他：`ecc:pm2`、`ecc:benchmark`、`ecc:ecc-tools-cost-audit`

## 横向去重决定汇总

| 张力 | 决定 | 备注 |
|------|------|------|
| Plan 多入口 | **全 keep，按场景自然分流** | gstack 偏评审 / ecc agent 偏拆解 / ecc command 偏快捷动作 |
| Review 多入口 | **全 keep，按场景自然分流** | gstack `/codex` 中立、ecc agent 自动触发、ecc command 一键 |
| E2E 重叠 | **drop** `ecc:e2e-runner` agent | 独家走 gstack `/qa /browse /design-review` |
| PR 重叠 | **drop** `ecc:pr` + `review-pr` commands | 独家走 gstack `/ship` |

## 已知问题 / 待校对

1. ~~**来源标注**：`claude-api`、`prompt-optimizer` 等 skill 是否真属 ecc 命名空间~~ → **已 resolve**：`claude-api` 是 Claude Code 内置 skill（不进 repo）；`prompt-optimizer` 在 ecc 里有，正常 vendor。详见 `docs/VENDORING-MANIFEST.md`。
2. **skill vs agent 混淆**：通用工作流组里我曾误把 `silent-failure-hunter`、`type-design-analyzer` 列为 skill — 它们是 agent，已纠正（在 Agents 节登记）。
3. ~~**`hookify-rules` 归类**：可能是 command 或 skill~~ → **已 resolve**：ecc 里实际是 skill，已从 commands 节删除，仅在 skills「通用工作流」组保留一次。
4. ~~**冷启动期偏宽**：v1 候选 ~137 项~~ → **已 resolve**：经归类修正、claude-api 删除、hookify-rules 去重后，v1 keep total 实际是 **135 项**（agents 31 / skills 73 / commands 31 = 29 from ecc + 1 fork + 1 原创）。4 周缩编预期不变。
5. **新增 — ralph-init 归类**：从 prior summary 默认的「user-level skill，install.sh 跳过」改为「用户原创 command，vendor 到 `commands/local/`」。详见 `docs/VENDORING-MANIFEST.md`。

## 冷启动期评估指标

冷启动期（v1 install 后 4 周）跟踪：

- **触发次数**：每个 agent / command 在 4 周内被实际调用几次
- **未触发列表**：0 次触发的项 → `attic/`
- **不熟悉列表**：知道存在但不会用的项 → 看是否值得学（保留学习意图的进 `attic/`，没意图的 drop）
- **空白发现**：4 周里有没有「想做这个事但 v1 里没合适工具」的瞬间 → 登记到 `docs/SOURCES.md` 作为外部引入候选

## 下一步

1. ~~**写 `scripts/vendor-from-ecc.sh`**~~（manifest review 完成后做）
2. **从 ecc vendor 132 项 + vendor ralph-init 到 `commands/local/`**
3. **写 `scripts/check-references.sh`** 跑 dangling 引用扫描
4. **Fork `plan-orchestrate.md`** 按 bare 架构改写（见 README 附录 A-H）
5. **写 `install.sh`** — 逐项 symlink 到 `~/.claude/`，含 `--dry-run` 和 `--backup`
6. **抓取上游 ecc commit hash** — 作为 v1 基线写入 `README.md`
7. **首次 install** — 跑 `./install.sh --backup`，与 ecc plugin 共存验证 bare 名字命中
8. **冷启动期开始日期** — install 完成日期记入 `README.md`
9. **4 周后** — 第一次缩编评估
