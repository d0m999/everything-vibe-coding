# 从散装安装迁移到 Local Marketplace

> 目标：把 `everything-vibe-coding` 改造成一个本地 marketplace，拆成 7 个主题 plugin，
> 用 `/plugin` 的原生 TUI 管理开关，按项目启用不同技能集。
>
> 状态：方案文档，尚未执行。日期：2026-07-14

---

## 0. 为什么要改

### 核心机制事实

Claude Code 里 **skill 没有单独的开关**——不存在 `disabledSkills` / `enabledSkills` 字段，官方也没打算做。
**唯一的开关粒度是 plugin。**

这决定了一切：所谓"轻量化管理 skills"，本质上等于"**把散装文件收编成若干个可开关的 plugin**"。

原生入口的真实能力（已核对官方文档）：

| 功能 | 交互式 TUI | 说明 |
|---|---|---|
| 插件 install / enable / disable / uninstall | ✅ **`/plugin`** | 四标签页，能只 disable 不卸载。**唯一真正的管理界面** |
| Subagent 管理 | ❌ | v2.1.198+ 已移除 TUI，只打印提示 |
| Hooks 配置 | ❌ | `/hooks` 只读展示，不能编辑 |
| MCP 服务器 | ✅ `/mcp` | |
| 设置 | ✅ `/config` | |
| Context 占用 | 🔍 `/context` | 只读，但能看清谁在吃 token |

**别再找"skill 管理 GUI"了，它不存在也不会有。把东西变成 plugin，`/plugin` 就是那个 GUI。**

### 当前负担

| 项 | 数量 | 代价 |
|---|---|---|
| ECC plugin skills | **278** | frontmatter 注入 system prompt ≈ **16.6k tokens** |
| ECC plugin agents | **67** | 另约 8–10k tokens |
| `~/.claude/skills` 实体目录 | 58（几乎全是 gstack） | 磁盘 1.2 GB |
| `~/.claude/skills` 符号链接 | 50 | 本仓库 `install.sh` 链进去的 |

**每个 session 开场即被吃掉 25–30k tokens，什么都还没干。**

### 三个必须处理的污染

1. **`~/.claude/plugin.json` 和 `~/.claude/marketplace.json` 是 ECC 的文件**，被它的安装脚本
   直接 cp 到了你的 `~/.claude/` 根目录（打开可见 `"name": "everything-claude-code"`，
   作者 Affaan Mustafa）。这等于把你整个 `~/.claude` 声明成了一个插件包。**必须删。**

2. **`~/.claude/hooks/`（`config-protection.js` / `quality-gate.js` / `hooks.json`）也是 ECC 的**。
   已确认 `settings.json` 完全没引用它们（里面全是 inline command）。死文件。

3. **`settings.json` 里 `"ecc@ecc": false` 已经关了 ECC，但当前进程还在加载它的 278 个 skill**——
   `settings.json.pre-slim.20260714-123906` 显示你今天 12:39 才关，CLI 进程是那之前启的，
   内存里还是旧配置。**重启即可验证。**

---

## 1. ⚠️ 迁移的唯一真实代价：slash command 会带前缀

**散装在 `~/.claude/commands/` 的命令没有前缀；放进 plugin 后会自动带上包名前缀。**

证据就在你当前会话里——ECC 的命令全是 `ecc:plan`、`ecc:code-review`，而你散装的是 `plan`、`code-review`，两组同时存在。

```
现在：  /plan          /ralph-init          /code-review
迁移后：/core:plan     /agentic:ralph-init  /core:code-review
```

**这是本次迁移唯一会让你不舒服的地方**，而且没法绕开（这是 Claude Code 的命名空间机制）。

**缓解：用短包名。** 所以本文档里包名是 `core` / `frontend` / `backend` / `agentic` / `ops` / `ios`，
而不是 `vibe-core` / `vibe-ios`。ECC 自己也是用 `ecc:` 短前缀，同理。

> 如果你更在乎命名空间的可读性，把包名改回 `vibe-*` 即可——代价只是每次多打 5 个字符。
> 包在 `enabledPlugins` 里的完整标识是 `core@evc`，即使短名也不会和别的 marketplace 撞。

Skills 也会带前缀（`core:coding-standards`），但那是 Claude 自己调用的，不影响你打字。

---

## 2. 立刻可做（30 秒，零风险，省 ~25k tokens）

```bash
# 退出 Claude Code，重新启动，然后：
/context
```

大概率 278 个 `ecc:` skill 直接消失。**不需要任何改造。**
如果重启后它们还在，说明是 `~/.claude/plugin.json` 在作祟，执行 §3.4 即可。

---

## 3. 清理阶段

### 3.1 🔴 卸载 ECC 之前：先捞走 Swift / iOS 资产

**你做 iOS，但仓库里只 vendor 了 `swift-build-resolver` / `swift-reviewer` 两个 agent，
一个配套 skill 都没有。ECC 里有 7 个值得拿——一旦 uninstall 就没了。**

```bash
ECC=~/.claude/plugins/marketplaces/ecc
DEST=~/Desktop/everything-vibe-coding/plugins/ios/skills

mkdir -p "$DEST"
for s in swiftui-patterns swift-concurrency-6-2 swift-actor-persistence \
         swift-protocol-di-testing foundation-models-on-device ios-icon-gen; do
  cp -R "$ECC/skills/$s" "$DEST/"
done
```

| skill | 大小 | 内容 |
|---|---|---|
| `swiftui-patterns` | 8K | SwiftUI 架构、`@Observable` 状态管理、view 组合、导航 |
| `swift-concurrency-6-2` | 8K | Swift 6.2 Approachable Concurrency、`@concurrent` |
| `swift-actor-persistence` | 8K | actor 线程安全持久化、文件后备缓存 |
| `swift-protocol-di-testing` | 8K | 协议式依赖注入、可测试性 |
| `foundation-models-on-device` | 8K | Apple FoundationModels 端侧 LLM、`@Generable` |
| `ios-icon-gen` | 28K | 从 SF Symbols 生成 Xcode imageset |

**`liquid-glass-design` 单独说**（iOS 26 Liquid Glass 设计系统，12K）：
你 `attic/skills/liquid-glass-design/` 里已经有一份，但 **diff 显示和 ECC 当前那份内容不同**——
ECC 更新过。做 iOS 26 的话这个该拿回来，并且用新版：

```bash
# 用 ECC 的新版覆盖 attic 里的旧版，并移入 ios 包
cp -R "$ECC/skills/liquid-glass-design" "$DEST/"
git rm -r attic/skills/liquid-glass-design
```

> ❌ **别误捞 `cisco-ios-patterns`**——那是思科网络设备的 IOS，跟 Apple 无关。
> ❌ **`flutter-reviewer` / `dart-build-resolver` 也跳过**——你做原生。

### 3.2 抢救 `PLUGIN_SCHEMA_NOTES.md`

ECC 留下的这份笔记记录了 plugin validator 的**未文档化硬约束**，是金子：

```bash
cp ~/.claude/PLUGIN_SCHEMA_NOTES.md \
   ~/Desktop/everything-vibe-coding/docs/PLUGIN_SCHEMA_NOTES.md
```

### 3.3 彻底卸载 ECC（不是 disable，是 uninstall）

```bash
claude plugin uninstall ecc@ecc
# 或 TUI：/plugin → Installed → ecc → Uninstall
```

然后手工删掉 `~/.claude/settings.json` 里的三处残留：

```jsonc
// env 里（ECC 卸载后无意义）
"ECC_DISABLED_HOOKS": "pre:bash:gateguard-fact-force,pre:edit-write:gateguard-fact-force"

// extraKnownMarketplaces 里
"ecc": {
  "source": { "source": "git", "url": "https://github.com/affaan-m/everything-claude-code.git" }
}

// enabledPlugins 里（uninstall 后应自动消失，确认一下）
"ecc@ecc": false
```

### 3.4 清掉 ECC 铺在 `~/.claude` 根目录的污染

> 🚨 **本节此前写的是 `rm -rf ~/.claude/hooks/`，那条指令现在会造成破坏，已删除。**
>
> commit `3eccc53` 把自研的 `quality-gate.js` / `config-protection.js` **symlink 进了
> 这个目录**，并在 `settings.json` 里注册了它们（PostToolUse 和 PreToolUse 各一处，
> 指向 `$HOME/.claude/hooks/*.js`）。整目录删会同时干掉这两个活的 symlink，
> 让两个 hook 静默失效。原注释「ECC 的，settings.json 完全没引用」已经过期。

```bash
rm ~/.claude/plugin.json              # ECC 的，会让 ~/.claude 被当成 plugin 根
rm ~/.claude/marketplace.json         # 同上
rm ~/.claude/PLUGIN_SCHEMA_NOTES.md   # 已在 §3.2 备份进仓库
```

`~/.claude/hooks/` 里的两个 ECC 遗留文件**已在 2026-07-14 单独删除**（`hooks.json`
引用 20+ 个不存在的 `scripts/hooks/*.js`；`README.md` 是 ECC 的通用 hooks 文档）：

```bash
# 已执行，此处仅作记录 —— 只删这两个文件，绝不要 rm -rf 整个目录
rm ~/.claude/hooks/hooks.json
rm ~/.claude/hooks/README.md
```

> ⚠️ 今后任何针对 `~/.claude/hooks/` 的清理，动手前先 `ls -la` 该目录，
> 确认哪些是 ECC 遗留的**普通文件**、哪些是本仓库 `install.sh` 建的**活 symlink**。
> 当前该目录里应当只剩两个 symlink（`quality-gate.js`、`config-protection.js`）
> 指回 `everything-vibe-coding/hooks/`，两者都是活的。

### 3.5 断开本仓库的 50 个旧 symlink

```bash
# dry run
find ~/.claude/skills ~/.claude/commands ~/.claude/agents -maxdepth 1 -type l

# 确认后（只删 symlink，不碰实体目录 —— gstack 是实体目录，不会被误删）
find ~/.claude/skills   -maxdepth 1 -type l -delete
find ~/.claude/commands -maxdepth 1 -type l -delete
find ~/.claude/agents   -maxdepth 1 -type l -delete
```

### 3.6 gstack：保持独立（已决定）

gstack 的 ~57 个 skill 是 cp 进 `~/.claude/skills/` 的**实体目录**，自成体系
（有独立的 `~/gstack` 运行时），在你的 `~/.claude/CLAUDE.md` 里明确在用。**不动它。**

**后果（可接受）：**

- gstack 的 skills **不受 plugin 开关控制，永久常驻 system prompt**
- 但成本很小——**约 1k tokens**，比 ECC 的 25k 小一个数量级
- 磁盘 1.2 GB 只是占地方，不影响 context

**结论：保持现状是对的决定。** 唯一建议是有空查一下那 1.2 GB 是什么
（`du -sh ~/.claude/skills/gstack/*/ | sort -rh | head`），多半是浏览器二进制或
`node_modules` 被一起 cp 进来了，能瘦身但不紧急。

---

## 4. Local Marketplace 结构

### 4.1 目录树

```
everything-vibe-coding/
├── .claude-plugin/
│   └── marketplace.json           ← 唯一的登记表
├── plugins/
│   ├── core/                      ← 全局常开
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   ├── commands/
│   │   └── agents/
│   ├── frontend/
│   ├── backend/
│   ├── agentic/
│   ├── loop/                      ← ralph / mempaw / autonomous loop，平常不开
│   ├── ops/
│   └── ios/                       ← 新增（你做 iOS）
├── attic/
└── docs/
```

原来的顶层 `skills/` `commands/` `agents/` **整体 `git mv` 进 `plugins/<包名>/`**，保留历史。

### 4.2 `.claude-plugin/marketplace.json`

字段格式已对照官方 `claude-plugins-official` 的真实文件确认。
**本地 plugin 的 `source` 是字符串相对路径**，不是对象：

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "evc",
  "description": "Curated Claude Code skills, commands and agents — themed plugins, toggle per project",
  "owner": {
    "name": "mempAw",
    "email": "wangd9434@gmail.com"
  },
  "plugins": [
    {
      "name": "core",
      "description": "语言无关的核心：规划、代码审查、重构、安全、验证、文档",
      "version": "1.0.0",
      "source": "./plugins/core",
      "category": "workflow"
    },
    {
      "name": "frontend",
      "description": "前端：设计系统、可访问性、界面手感、TypeScript 审查",
      "version": "1.0.0",
      "source": "./plugins/frontend",
      "category": "development"
    },
    {
      "name": "backend",
      "description": "后端与数据：Python / FastAPI / Postgres / Redis / 迁移 / ML",
      "version": "1.0.0",
      "source": "./plugins/backend",
      "category": "development"
    },
    {
      "name": "agentic",
      "description": "Agent 与 LLM 应用开发：harness 设计与审计、eval、skill 治理、hookify、编排",
      "version": "1.0.0",
      "source": "./plugins/agentic",
      "category": "development"
    },
    {
      "name": "loop",
      "description": "长跑自治循环：ralph-init、mempaw-loop、autonomous loop 模式与运维。低频重型，按需开",
      "version": "1.0.0",
      "source": "./plugins/loop",
      "category": "development"
    },
    {
      "name": "ops",
      "description": "部署与运维：Docker、部署模式、canary、E2E、视频提取",
      "version": "1.0.0",
      "source": "./plugins/ops",
      "category": "deployment"
    },
    {
      "name": "ios",
      "description": "iOS / Swift：SwiftUI、Swift 6.2 并发、actor 持久化、Liquid Glass、图标生成",
      "version": "1.0.0",
      "source": "./plugins/ios",
      "category": "development"
    }
  ]
}
```

`marketplace.json` **必须放在 `.claude-plugin/` 下**（官方就是这个位置）。

### 4.3 每个包的 `.claude-plugin/plugin.json`

**最安全的写法：完全不写 `skills` / `commands` / `agents` / `hooks` 字段**，全靠目录约定自动加载。
官方 `telegram` plugin 就是这么干的——它只有一个 `skills/` 目录，plugin.json 里一个组件字段都没有：

```json
{
  "name": "core",
  "description": "语言无关的核心：规划、代码审查、重构、安全、验证、文档",
  "version": "1.0.0",
  "author": { "name": "mempAw" },
  "keywords": ["planning", "code-review", "security", "refactor"]
}
```

> ### ⚠️ Validator 的四个硬约束（来自 `PLUGIN_SCHEMA_NOTES.md`，血泪总结）
>
> 如果你**非要**显式声明组件路径：
>
> 1. **`version` 必填**，缺了安装时失败。
> 2. **`agents` / `commands` / `skills` / `hooks` 必须是数组**，字符串一律拒绝。
> 3. **`agents` 不接受目录路径**——`["./agents/"]` 会失败，必须逐个列文件：
>    `["./agents/planner.md", "./agents/code-reviewer.md", ...]`。最常见的报错来源。
> 4. **绝对不要写 `"hooks"` 字段。** Claude Code v2.1+ 会**自动按约定加载** `hooks/hooks.json`，
>    再声明一次就报 `Duplicate hooks file detected`。ECC 为这个来回改了 4 次。
>
> 报错通常只有一句含糊的 `Invalid input`，不告诉你根因。
> **所以：不写组件字段，靠约定，最省事也最不容易错。**

```bash
claude plugin validate plugins/core/.claude-plugin/plugin.json
```

---

## 5. 归属分配（55 skills / 26 commands / 29 agents）

> skills 从 48 涨到 55，因为 §3.1 从 ECC 捞了 7 个 Swift/iOS 的。
> （48 = 当前仓库有效 skill 数，已排除 `gateguard`——已被 1d45347 删除——和
> `continuous-learning-v2`——SKILL.md 已被 65225ab 删除，仅剩一个空壳 `scripts/`
> 目录，不是可用 skill。）

### `core` — 13 skills / 11 commands / 17 agents（全局常开）

**skills**
`architecture-decision-records` `codebase-onboarding` `coding-standards` `documentation-lookup`
`error-handling` `plankton-code-quality` `prompt-optimizer` `repo-scan`
`safety-guard` `security-review` `security-scan` `strategic-compact` `verification-loop`

**commands**
`plan` `plan-prd` `code-review` `build-fix` `refactor-clean` `security-scan` `test-coverage`
`update-docs` `update-codemaps` `learn` `model-route`

**agents**
`planner` `architect` `code-architect` `code-explorer` `code-reviewer` `code-simplifier`
`comment-analyzer` `build-error-resolver` `refactor-cleaner` `security-reviewer`
`silent-failure-hunter` `type-design-analyzer` `tdd-guide` `doc-updater` `docs-lookup`
`pr-test-analyzer` `performance-optimizer`

### `frontend` — 5 skills / 2 agents

**skills** `accessibility` `design-system` `frontend-patterns` `frontend-design-direction` `make-interfaces-feel-better`
**agents** `a11y-architect` `typescript-reviewer`

### `backend` — 10 skills / 2 commands / 5 agents

**skills** `api-design` `fastapi-patterns` `python-patterns` `python-testing` `postgres-patterns`
`redis-patterns` `database-migrations` `hexagonal-architecture` `pytorch-patterns` `mle-workflow`
**commands** `fastapi-review` `python-review`
**agents** `database-reviewer` `fastapi-reviewer` `python-reviewer` `pytorch-build-resolver` `mle-reviewer`

> ML 那 4 个（`pytorch-patterns` `mle-workflow` `pytorch-build-resolver` `mle-reviewer`）暂归 backend。
> ML 做得多的话值得单开第 7 个包 `ml`。

### `agentic` — 12 skills / 7 commands / 1 agent

做 agent / LLM 应用时开。**日常开发用的那部分**（harness 设计、eval、skill 治理、hookify）。

**skills** `agent-architecture-audit` `agent-eval` `agent-harness-construction`
`agent-introspection-debugging` `agentic-engineering` `agentic-os` `ai-regression-testing`
`eval-harness` `hookify-rules` `skill-comply` `skill-scout` `skill-stocktake`

**commands** `hookify` `hookify-configure` `hookify-help` `hookify-list`
`learn-eval` `plan-orchestrate` `skill-create`

**agents** `harness-optimizer`

> `plan-orchestrate` 留在这里而不是 `loop`：它虽然是 loop 链的上游
> （`/plan-orchestrate` → `/mempaw-loop-plan` → `/mempaw-loop-start`），
> 但能独立用来生成 Agent 调用块和并行波次图。跑 loop 时 `agentic` + `loop` 一起开即可。

### `loop` — 4 skills / 6 commands / 1 agent（**平常不开**）

长跑自治循环的全套：ralph、mempaw、autonomous loop。低频、重型，**只在真要跑 loop 时才开**。
这是把它从 `agentic` 拆出来的全部意义——日常做 agent 开发不该为这套东西付 context。

**skills** `autonomous-loops` `continuous-agent-loop` `autonomous-agent-harness` `ralphinho-rfc-pipeline`

**commands** `loop-start` `loop-status` `mempaw-loop-plan` `mempaw-loop-start` `mempaw-loop-status`
**`ralph-init`**（含 `ralph-init/` 的 references + scripts + fixtures）

**agents** `loop-operator`

> **`commands/local/` 就是 `ralph-init`。** install.sh 的注释写着
> `commands/local/ (originals — ralph-init etc.)`——`local/` 是"我自己原创的，不是 vendor 来的"的分组约定
> （对比 `cc1eed9 feat: v1 vendoring — 135 项`）。它带一整套 references + 4 个 Python/shell 校验脚本
> + valid/invalid fixtures，已在 git 里。**迁移时整个 `ralph-init.md` + `ralph-init/` 目录搬进
> `plugins/loop/commands/`，扁平化掉 `local/` 这一层**（install.sh 本来就是这么平铺的）。

### `ops` — 4 skills / 1 agent

**skills** `deployment-patterns` `docker-patterns` `canary-watch` `video-extract`
**agents** `e2e-runner`

### `ios` — 7 skills / 2 agents（新增）

**skills**（全部来自 §3.1 从 ECC 捞的）
`swiftui-patterns` `swift-concurrency-6-2` `swift-actor-persistence` `swift-protocol-di-testing`
`foundation-models-on-device` `ios-icon-gen` `liquid-glass-design`

**agents** `swift-build-resolver` `swift-reviewer`

> 你的 gstack 另有 `/ios-qa` `/ios-fix` `/ios-clean` `/ios-design-review` `/ios-sync`——
> 那套保持独立（§3.6），和这个包互补，不冲突。

### 删除

| 文件 | 处理 |
|---|---|
| `commands/ecc-guide.md` | ✅ 已删（44fdfdc）——ECC 都卸载了，这个向导没意义 |

---

## 6. 安装与启用

### 6.1 注册本地 marketplace

```bash
claude plugin marketplace add ~/Desktop/everything-vibe-coding
```

之后 `/plugin` → Marketplaces 里能看到 `evc`，Discover 里能看到 7 个包。

### 6.2 全局常开 core

`~/.claude/settings.json`：

```jsonc
{
  "enabledPlugins": {
    "core@evc": true
  }
}
```

> `extraKnownMarketplaces` 里本地 directory source 的准确字段，**跑一次
> `claude plugin marketplace add` 后回读 `settings.json` 看它实际写成什么，然后照抄**——
> 这是本文档唯一没有实证的字段，别硬猜。

### 6.3 按项目启用（最大收益）

各项目的 `.claude/settings.json`：

```json
// iOS 项目
{ "enabledPlugins": { "ios@evc": true } }

// Python 后端
{ "enabledPlugins": { "backend@evc": true } }

// 前端
{ "enabledPlugins": { "frontend@evc": true, "ops@evc": true } }

// 这个仓库自己（agent / skill 治理）
{ "enabledPlugins": { "agentic@evc": true } }
```

`core` 已全局开，项目级只追加需要的。

**`loop` 永远不进任何项目的常驻配置。** 真要跑 ralph / mempaw loop 时，临时开：

```bash
/plugin enable loop@evc
# 跑完
/plugin disable loop@evc
```

这样那 4 个 skill + 6 个 command + `loop-operator` 平时一个 token 都不占。

### 6.4 日常管理

```
/plugin     ← 这就是你要的那个界面
/context    ← 看谁在吃 token
```

---

## 7. `install.sh` 怎么办

**不再需要它做安装**——`claude plugin marketplace add` 取代了 symlink。

建议改成 `--uninstall-legacy` 清理脚本，专门断开 §3.5 的旧 symlink，方便你（和 fork 你仓库的人）迁移。
或直接删掉，README 里写清新装法：

```bash
claude plugin marketplace add https://github.com/<you>/everything-vibe-coding
# 然后 /plugin 里勾选想要的包
```

---

## 8. 验证与回滚

```bash
# 每个包过一遍 validator
for p in plugins/*/; do claude plugin validate "$p/.claude-plugin/plugin.json"; done

# 重启 Claude Code，对比 context
/context
```

**预期：开场 context 从 ~30k 降到 ~4–6k**（core + gstack 常驻）。

**回滚**：`settings.json` 已有多个自动备份（`settings.json.backup*` / `.pre-slim.*`）；
改造全程在 git 里做，`git mv` 保留历史，随时 revert；旧 symlink 装法可用 `install.sh --apply` 重新链回来。

---

## 9. 收益汇总

| | 改造前 | 改造后 |
|---|---|---|
| 开场 context | ~30k tokens | ~4–6k（core + gstack） |
| skill 开关粒度 | 无（全有或全无） | 7 个主题包，`/plugin` 勾选 |
| 按项目裁剪 | 不可能 | `.claude/settings.json` 一行 |
| 管理界面 | 无 | `/plugin` TUI |
| 卸载 | 手工删 symlink | `/plugin uninstall` |
| `~/.claude/skills` | 58 目录 + 50 链接 | 只剩 gstack（有意保留） |
| iOS 支持 | 2 个 agent，0 个 skill | 7 skills + 2 agents |
| 版本化 / 分发 | 靠 install.sh | git + marketplace，别人一行装 |
| **代价** | — | **slash command 带前缀**（`/core:plan`），见 §1 |
