> 生成于 2026-07-14。对比基准：本仓库 HEAD (3eccc53) vs ECC 本地副本 (ed38744, VERSION 2.0.0)。
> 由 9 个并行审计 agent 产出，含 6 个 drift 维度 + 2 个新增机会扫描 + 1 次综合裁决。

# ECC 同步状况综合报告

## 1. 直接答案

**没有。一次都没有。**

本仓库停在 2026-05-16 的 commit `cc1eed9`,那次从 ECC 的 `2.0.0-rc.1` 一次性 vendor 了 135 项组件,之后 59 天内**没有任何一次上游同步**。期间 ECC 从 rc.1 走到了 2.0.0 正式版(HEAD 提交时间就是今天),规模变成 278 skills / 67 agents / 94 commands。

对照:

| | 本仓库 | ECC 当前 | 缺口 |
|---|---|---|---|
| skills | 50(其中 `video-extract` 自研 → 49 来自 ECC) | 278 | 229 |
| agents | 29(**零个自研**,是 67 的严格子集) | 67 | 38 |
| commands | 31(其中 5 个自研:`mempaw-loop-*` ×3、`plan-orchestrate`、`local/ralph-init`) | 94 | 68 |
| hooks | 2(**都是自研**) | 50(在 `scripts/hooks/`) | — |

`agents/` 目录零自研这一点值得单独说:它 100% 是 ECC 的镜像,所以它也 100% 地继承了 ECC rc.1 的全部缺陷,没有任何本地修正抵消。

---

## 2. 唯一的例外:今天的 hooks commit `3eccc53` 算不算"根据 ECC 更新"?

**不算。它既不是新版,也不是旧版遗留物 —— 它是自研重写。**

`hooks/quality-gate.js` 和 `hooks/config-protection.js` 不是从 ECC 拷来的。ECC 的同名实现在 `scripts/hooks/` 下(不在 `hooks/` 下),而且**仓库版本比 ECC 版本强**:

- **config-protection.js**:仓库版多保护 5 个 ECC 未覆盖的配置文件(`setup.cfg`、`.flake8`、`mypy.ini`、`.golangci.yml`、`.golangci.yaml`);用的是现代 PreToolUse 协议(`hookSpecificOutput.permissionDecision: 'deny'` + exit 0),ECC 还在用老式 exit code 2 + stderr;提供 `ALLOW_CONFIG_EDIT=1` 逃生舱,ECC 只能"临时把 hook 关掉";ECC 那个 lstat/ENOENT fail-closed 修复,仓库版本来就有。
- **quality-gate.js**:ECC 版 `require('../lib/resolve-formatter')`,直接拷进 `~/.claude/hooks/` 会因为找不到 `../lib` 而崩溃;即使连 lib 一起 vendor,默认配置下它几乎是 no-op(不设 `ECC_QUALITY_GATE_FIX=true` 不格式化,不设 `ECC_QUALITY_GATE_STRICT=true` 连日志都不打,而且**完全跳过 JS/TS**)。仓库版自包含,按项目实际配置(biome/prettier/ruff/gofmt)格式化,并把残留 lint 问题通过 `additionalContext` 回灌给模型。

所以 `3eccc53` 是"从 ECC 学了思路、自己写了更好的版本",反向同步(用 ECC 覆盖)只会让你丢掉 5 个保护目标、丢掉逃生舱、退回旧协议。**KEEP_LOCAL,不要动。**

**真正的旧版遗留物在别处,而且有三处,都不在仓库里:**

1. `~/.claude/hooks/hooks.json`(5/29,11832 bytes)—— ECC 旧安装脚本 `cp` 进来的,里面引用 `session-start.js`、`post-edit-format.js`、`insaits-security-wrapper.js` 等 20+ 个 ECC 脚本路径。
2. `~/.claude/hooks/README.md`(3/26,8700 bytes)—— 同上。
3. `~/.claude/settings.json:5` 的 `"ECC_DISABLED_HOOKS": "pre:bash:gateguard-fact-force,pre:edit-write:gateguard-fact-force"` —— 它在禁用一个**根本没有被安装的 hook**。

前两个目前是惰性的(settings.json 不引用,`~/.claude/` 也不是 plugin 目录,不会被自动加载),但它们会让人误以为那批 ECC hook 还在生效。三个都该删。

---

## 3. 代价:不同步的实际后果

我按"是否真的会在你的会话里造成行为差异"重新排了序,而不是按审计给的 priority 标签。

### 3.1 你的仓库正在教 Claude 写错代码(每天都在生效,总修复量 < 15 行)

这五处是最高优先级,因为它们不是"上游有新功能",而是**你分发出去的参考实现本身是坏的**,而这些 skill/agent 的全部作用就是给模型抄:

| 组件 | 坏在哪 | 照抄的后果 |
|---|---|---|
| `skills/frontend-patterns` | `useFetch` 的 `refetch` 用了 `useCallback(..., [fetcher, options])`,调用方传内联函数/对象字面量时每次渲染都重建 refetch → 下游 useEffect 反复触发 | **无限 fetch 循环**,打爆后端 + 组件卡死。上游改用 `fetcherRef`/`optionsRef` + 空依赖数组 |
| `skills/coding-standards` | (1) Zod `error.errors`,v4 已改名为 `.issues`;(2) `markets.sort()` 原地排序 | (1) 校验错误详情静默变 `undefined`,正好踩中你 `common/coding-style.md` 禁止的"静默吞掉错误";(2) 基线规范文件自己违反自己写的 `Immutability (CRITICAL)` 铁律 |
| `skills/security-review` | 同样的 Zod `error.errors` | 一个"安全审查"skill 教出来的输入校验代码本身丢错误信息 |
| `skills/python-patterns` | EAFP/LBYL 核心示例的 `get_value(dictionary, key)` 函数体里 `return default_value`,该名字未定义 | **NameError**,示例根本跑不通。这是该 skill 最核心的那个例子 |
| `agents/performance-optimizer.md` | `getCLS/getFID/getLCP/...` 是 web-vitals v3 API | v4 已**删除**全部 `get*` 导出,import 直接崩;FID 自 2024-03 起已不是 Core Web Vital,agent 会引导你去优化一个 Google 已下线的指标,并漏掉真正的 INP |

### 3.2 权限过宽(改 1 行 frontmatter)

`agents/security-reviewer.md` 和 `agents/database-reviewer.md` 的 `tools` 是 `["Read","Write","Edit","Bash","Grep","Glob"]`。已 grep 确认两者正文**从头到尾没有任何一处使用 Write/Edit** —— 纯粹多余的授权。上游收窄为 `["Read","Grep","Glob","Bash"]`。一个能直接改 schema/migration 的"数据库审查 agent",和一个只想要审查报告却能擅自改代码的"安全审查 agent",在自动化 loop 里都是实打实的风险。零行为损失。

### 3.3 悬空 / 失效引用

- **`commands/security-scan.md` 的 `agent: everything-claude-code:security-reviewer`** —— 你环境里根本没有叫 `everything-claude-code` 的 plugin,这个命令的 agent **当前解析不到**。这是全仓库唯一一处带命名空间的 `agent:` 引用。注意:上游改成 `ecc:security-reviewer` 对你**同样无用**(你的 agent 是 install.sh 平铺 symlink 到 `~/.claude/agents/<name>.md` 的裸文件,不走 plugin 命名空间)。正确修法是写裸名 `security-reviewer`。这是本次分析里最该立刻动手的真 bug。
- **`agents/build-error-resolver.md` 指向 `code-architect`** —— 不是悬空(两个 agent 本地都在),是路由错了对象。`architect`(opus、只读)做架构决策,`code-architect`(sonnet)做实现蓝图。build 失败后需要的是架构判断,你现在拿到的是文件清单。
- **`commands/hookify.md:19` 依赖 `conversation-analyzer` agent,该 agent 从未 vendor** —— `docs/LOCAL-PATCHES.md` 自己也承认这是已知断链。`/hookify` 的零参数路径是坏的。

### 3.4 四个"文档在、引擎不在"的空壳(结构性问题,不是 drift 造成的)

这批不是"上游改了你没跟",而是 **vendoring 时整棵 `scripts/` 树没拿**,导致命令/skill 的说明书在,机器不在:

- **`/cost-report`** —— 查 `~/.claude-cost-tracker/usage.db`,这台机器上不存在,而且仓库里没有任何东西会写它。执行只会输出 "Database not found"。上游已改成读 `~/.claude/metrics/costs.jsonl`(这个文件真实存在、3.6 MB、今天还在写),但**那是 ECC 的 `scripts/hooks/cost-tracker.js` 写的** —— 卸载 ECC 后同样断流。只同步 .md 等于把一个死命令换成另一个死命令。
- **`/harness-audit`** —— 调 `node scripts/harness-audit.js`,而 `scripts/` 下只有 `check-references.sh`、`generate-codex-command-skills.sh`、`vendor-from-ecc.sh` 三个 shell。死命令。
- **`/skill-health`** —— 调 `$ECC_ROOT/scripts/skills-health.js`。死命令。而且上游新版还引入了对未 vendor 的 `scripts/lib/resolve-ecc-root` 的新依赖,同步反而加深对 ECC 的耦合。
- **`skills/gateguard`** —— SKILL.md 里那句"The hook at `scripts/hooks/gateguard-fact-force.js` is included in this plugin"在本仓库是**假的**(那是个 41KB / 1278 行的脚本,从未 vendor)。所以你的 gateguard 从来没拦截过任何一次 Edit/Write/Bash。讽刺的是 `settings.json:5` 还留着 `ECC_DISABLED_HOOKS` 在禁用它。
- **`skills/strategic-compact`** —— SKILL.md(新旧两版都)引用 `suggest-compact.js`,但仓库里躺的是一个**没人引用的** `suggest-compact.sh`(54 行,纯数工具调用次数)。上游把触发逻辑重写成了"读 transcript 的真实 token 用量"(累加 `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`,200k 窗口阈值 160k,**1M 窗口阈值 250k**,靠模型名里的 `[1m]` 标记自动识别窗口,之后每再涨 60k 提醒一次)。**你现在跑的就是 `claude-opus-4-8[1m]`** —— 旧的"50 次工具调用就提示 compact"在 1M 窗口下是纯噪音,而新逻辑正是为你这个窗口写的。

### 3.5 continuous-learning-v2:我要推翻两个审计维度的严重性判断

两个维度都把 `observe.sh` 的 ReDoS(密钥脱敏正则灾难性回溯,能让 python 进程 100% CPU 卡死整个会话)和 `observer-loop.sh` 的 macOS `mktemp` 硬故障(BSD 上模板只替换结尾的 X 串 → 第二个 cycle 必然 "File exists" 失败)标成 **high**,理由是"你在 Darwin 上,这是硬故障"。

**我实测了 `~/.claude/settings.json`,这个判断是错的。** 你的 hooks 注册里只有:

- PostToolUse `Write|Edit|MultiEdit` → 你自己的 `quality-gate.js`
- PreToolUse `Write|Edit|MultiEdit` → 你自己的 `config-protection.js`
- PreToolUse `Bash` → `npx block-no-verify@1.1.2`(第三方,不来自本仓库)
- 其余全是 vibe-island / claudio 的通知桥

**CL v2 的 hook 一个都没注册**(`grep -rln "observe.sh"` 在 settings.json 里零命中,只在 CL v2 自己的 4 个文件里互相引用)。所以:

- ReDoS 是**休眠**的 —— `observe.sh` 从未被调用过一次
- macOS mktemp bug 是**休眠**的 —— observer 从未启动过
- `instinct-cli.py` 的 SSRF(`urllib.request.urlopen(source)` 裸调用,允许 `http://`、不校验目标主机、无超时、无大小上限)**只有你手动执行 `instinct import <url>` 时才触发**

结论:**CL v2 在你机器上是 100% 惰性的死代码。12 个被 git 跟踪的文件、约 2000 行 Python + shell,从来没有跑过,也从来没有学到过任何东西。** 它同时还是全仓库唯一的真实安全债。

这就把问题从"要不要同步 6 个文件"变成了**"用还是删"的二选一**,见下面 P2。

(`skills/skill-comply/scripts/runner.py` 的 `setup_commands` 任意命令执行是同类:只有你真跑 `/skill-comply` 且 scenario 来自不可信来源才触发。但上游的修复只有 8 行白名单,属于极廉价加固,无论如何该收。)

### 3.6 唯一的纯能力升级:fastapi-patterns(且两个审计维度在这里打架)

一个维度说"纯内容升级,无外部依赖,可整文件覆盖";另一个说"上游删掉了本地独有内容,必须合并"。**后者对,我按后者裁决。**

上游整篇重写(+328/-171),工程质量确实更高:pydantic-settings 配置层、独立 `services/` 服务层、依赖 DB 唯一约束 + 捕获 `IntegrityError`(替代有竞态的应用层预检)、分页强制 `order_by`、JWT 载荷防御式解析、认证(401) 与授权/停用(403) 分离、`Annotated` 类型别名依赖、完整的 pytest+httpx conftest fixture 链、Anti-Patterns 章节。

但它**同时删掉了**本地版独有的:CORS `allow_origins=["*"]` + `allow_credentials=True` 的浏览器拒绝警告、OpenAPI 自定义章节、Security Checklist、Performance Checklist,以及指向本仓库**确实存在的** `fastapi-reviewer` agent 和 `/fastapi-review` 命令的 See Also。

**裁决:合并,不覆盖。** 取上游正文,把这四块本地内容重新贴回去。

---

## 4. frontmatter schema:扁平 `origin:` 是不是必须修的问题?

**不是。不要为此批量改 50 个文件。**

证据链:

1. Claude Code 官方 frontmatter 字段表(name / description / when_to_use / argument-hint / arguments / disable-model-invocation / user-invocable / allowed-tools / disallowed-tools / model / effort / context / agent / hooks / paths / shell)里,**`origin` 和 `metadata` 都不存在**,而且明确写着 "All fields are optional"。未知键一律静默忽略,CLI 二进制里搜不到任何 unknown-key 告警字符串。
2. 唯一的失败模式是 **YAML 语法错误**("loads with empty metadata, all frontmatter fields silently dropped"),而扁平 `origin: ECC` 是合法 YAML。
3. 实证:`~/.claude/skills/*` 全部 symlink 指向本仓库,其中 48 个带扁平 `origin:`,**本次会话中全部正常加载、description 正确、零告警**。
4. 上游自己也不一致:278 个 skill 里还有 7 个是扁平 `origin:`,而且 ECC 的 `docs/SKILL-DEVELOPMENT-GUIDE.md` 至今仍在模板和字段表里教扁平写法,没有任何测试校验它。

嵌套 `metadata.origin` 只是 ECC 向 agentskills.io 开放标准对齐的**内部约定**,不是 Claude Code 的要求。只有当你以后要跑 `skills-ref validate` 或往 agentskills registry 发布时,才有做美观对齐的理由。

**但这里有一个真的 schema bug(与上游无关,是本地待修项):** `skills/agent-eval`、`skills/agent-architecture-audit`、`skills/eval-harness`、`skills/skill-comply` 四个 SKILL.md 的 frontmatter 用了 `tools: Read, Write, Edit, Bash, Grep, Glob`。但 skill 的官方字段是 **`allowed-tools`**(`tools:` 是 **agent** 的字段)。这四处声明**完全不生效**,被静默忽略。上游 ECC 有一模一样的错误,所以它不是同步项 —— 要修就本地把 `tools:` 改成 `allowed-tools:`。

---

## 5. 最大缺口:iOS / Swift

**事实:** 仓库有 `swift-reviewer` 和 `swift-build-resolver` 两个 agent,**零个 Swift skill**。而且 ECC 新增的 38 个 agent / 68 个 command 里**没有任何一个**与 Swift/iOS 相关 —— 缺口 100% 在 skills 层,补 agent/command 对 iOS 零收益。

ECC 有 6 个直接可用、且没有任何外部依赖的 Swift/iOS skill:

| skill | 大小 | 为什么值得 |
|---|---|---|
| `swiftui-patterns` | 8K | SwiftUI 架构、`@Observable` 状态管理、view 组合、导航、性能。iOS 原生开发的基础参考层,填最大的洞 |
| `swift-concurrency-6-2` | 8K | Swift 6.2 Approachable Concurrency(默认单线程、`@concurrent` 显式后台、isolated conformances)。**模型训练数据在这块经常给出过时写法** |
| `swift-protocol-di-testing` | 8K | protocol 依赖注入 + Swift Testing mock。你的全局 rules 把 80% 覆盖率和 TDD 定为 MANDATORY,但**没有任何 Swift 侧测试 skill 支撑** —— 这是 rules 与实际能力之间的断层 |
| `swift-actor-persistence` | 8K | 用 actor 做线程安全持久化,从设计上消除 data race。与 concurrency-6-2 配套 |
| `foundation-models-on-device` | 8K | Apple FoundationModels 端侧 LLM(`@Generable` 引导生成、tool calling、snapshot streaming,iOS 26+)。**正好落在你两条主线(iOS 原生 + LLM 应用)的交叉点**,是整份清单里最独特的一项 |
| `liquid-glass-design` | 12K | iOS 26 Liquid Glass 设计系统。gstack 的 `ios-design-review` 只是审计流程,没有设计语言参考;这是当前 iOS 的主流视觉语言,**知识截止后的新 API,模型自己编不出来** |

合计 52K 磁盘。

**关于 context 开销,一个必须澄清的点(直接关系到你的迁移动机):**

skill 在待机时只把 frontmatter 的 `name` + `description` 送进系统提示,**正文只有被触发时才读**。ECC 的 278 个 skill 吃掉约 25k tokens,平均每个 ≈ 90 tokens 的索引行。再加 6 个 Swift skill ≈ **+540 tokens 的常驻索引开销**,那 52K 正文只在你真的写 Swift 时才进 context。

所以"补 Swift"和"省 context"**不矛盾**。你真正的 token 节省(278 → 50)在 5/16 vendoring 那天就已经拿到了。

`liquid-glass-design`、`swift-concurrency-6-2`、`foundation-models-on-device` 这三个尤其值得 —— 它们是"模型训练数据里没有或已过时的新 API",这是本地 skill 收益最高的那一类。gstack 的 `ios-qa` / `ios-design-review` / `ios-fix` 是**流程与审计**侧,不覆盖**语言与框架参考**侧,两者不重叠。

---

## 6. 建议的动作顺序

### 排序原则(先讲清楚,免得白做)

**内容修复与 plugin 化迁移是正交的。** 迁移改变的是"怎么被加载"(命名空间、hooks 自动发现、install.sh 的软链),**不改变文件内容**。所以 P0/P1 的 bug 修复、权限收敛、死组件清理,现在做不会被迁移作废。

**只有两件事和迁移耦合**,必须压到迁移那一步一次做完,否则会返工:
1. **新 hook 的注册方式**(settings.json 手工注册 vs `hooks/hooks.json` 自动加载)
2. **command 里 `agent:` 是裸名还是 `<plugin>:name` 前缀**

**还有一条必须说破:plugin 化本身不省 context。** 278 → 50 的 token 节省你已经拿到了。plugin 化的收益是安装、分发、命名空间、hooks 自动加载 —— **不是 token**。别把它当成 context 优化项去排期。真正还能省 context 的是继续**删**(见 P1、P2),不是迁移。

---

### P0 — 止血(今天,约 15 行改动 + 1 个文件替换,与迁移完全无关)

1. **五处"教错代码"**:
   - `skills/frontend-patterns`:`useFetch` 改用 `fetcherRef`/`optionsRef` + 空依赖数组,`markets.sort()` → `[...markets].sort()`
   - `skills/coding-standards`:`error.errors` → `error.issues`,`markets.sort()` → `[...markets].sort()`
   - `skills/security-review`:`error.errors` → `error.issues`
   - `skills/python-patterns`:`get_value` 签名补上 `default_value: Any = None`(两处)
   - `agents/performance-optimizer.md`:`get*` → `on*`,FID(<100ms) → INP(<200ms)
2. **权限收敛**:`agents/security-reviewer.md` + `agents/database-reviewer.md` 的 `tools` 删掉 `Write` 和 `Edit`
3. **`commands/security-scan.md`** → `agent: security-reviewer`(裸名。迁移后若决定启用 plugin 命名空间,再改一次,成本 1 行)
4. **`agents/build-error-resolver.md`** → 升级路径指向 `architect` 而不是 `code-architect`
5. **成本优化**:`agents/comment-analyzer.md` + `agents/docs-lookup.md` → `model: haiku`(与你自己 `rules/common/performance.md` 的选型原则一致,调用成本降至约 1/3;git 历史确认这两行从未被本地改过,是上游调优)
6. **`skills/skill-comply/scripts/runner.py`**:收上游的 `ALLOWED_SETUP_EXECUTABLES` 白名单(8 行)

### P1 — 清死组件(比同步更值钱:直接砍掉误导面 + 减少 skill/command 索引行)

7. **`git rm commands/ecc-guide.md`** —— 它导航的是 ECC 的 `agent.yaml`、`manifests/`、`hooks/hooks.json`、`scripts/ci/catalog.js`,本仓库**一样都没有**;它推荐的 `/harness-audit`、`/skill-health` 本身也是坏命令。在"不再使用 ECC"的前提下,它唯一的效果是让 Claude 在你项目里到处翻找不存在的 ECC 文件。顺带清理 `scripts/vendor-from-ecc.sh:105` 和 `docs/VENDORING-MANIFEST.md:151` 的条目。(`docs/PLUGIN-MIGRATION.md:428` 已独立得出同样结论 —— 两条分析路径互相印证。)
8. **`/cost-report`、`/harness-audit`、`/skill-health` 三个死命令:补引擎脚本还是删?** 我建议**删**。三个都依赖 ECC 的 `scripts/` 树,而"零依赖、不依赖 plugin/node_modules/ECC root 解析"正是你 `3eccc53` 那个 commit 的明确设计目标。
9. **`skills/gateguard`:vendor 41KB 的 `gateguard-fact-force.js`,还是删?** 我建议**删**(或至少在 SKILL.md 顶部标注"参考文档,本仓库未包含 hook,不会生效")。它与零依赖目标冲突,而且你 `settings.json:5` 那行 `ECC_DISABLED_HOOKS` 说明你本来就把它关了。顺手把那行失效的环境变量一起删掉。
10. **删 `~/.claude/hooks/hooks.json` 和 `~/.claude/hooks/README.md`** —— ECC 旧安装脚本的遗留物,引用 20+ 个不存在的脚本路径,虽然不会被执行但极具误导性。
11. **`dos2unix skills/repo-scan/SKILL.md`** —— CRLF/LF 混合行尾,导致每次 diff 都误报 +44/-63。

### P2 — 一个必须由你拍板的取舍:continuous-learning-v2

**前提事实(见 3.5):它在你机器上从未运行过,一个 hook 都没注册,零 instinct。**

- **若决定用**:必须**原子性**同步 8 个文件 —— `instinct-cli.py`(整文件,1519 → 1956 行)、`test_parse_instinct.py`(捆绑,是验证替换正确性的唯一手段)、`observe.sh`、`observer-loop.sh`、`start-observer.sh`、`detect-project.sh`、`scripts/lib/homunculus-dir.sh`、`migrate-homunculus.sh`。**`_ecc_` → `_clv2_` 是成对重命名,漏掉任何一个就 `command not found`,整个 skill 崩。** 然后补 4 个命令让它闭环(`/evolve`、`/instinct-status`、`/promote`、`/projects`,共约 317 行;`instinct-export`/`import` 可选),最后把 `observe.sh` 接进 settings.json。
- **若决定不用**:`git rm -r skills/continuous-learning-v2` —— SSRF、ReDoS、macOS mktemp 三个问题一次性消失,还省一行 skill 索引和 12 个跟踪文件。

**我的倾向:如果它三个月没被启用过,删。** 理由:它是全仓库最重的单块(12 文件、约 2000 行),而你已经有 `skill-scout` / `skill-stocktake` / `learn` / `learn-eval` 四条学习路径。反面理由也很实在:你做 agent/skill 治理,`/evolve`(把累积的 instinct 聚类成新 skill/command)这个收敛闭环确实对口 —— 但**没有 `/evolve` 的 CL v2 只能观察不能收敛,而现在连观察都没开**。

(附:上游 `observer.md` 把 instinct 晋升门槛从"每个 instance 的 confidence 都 ≥ 0.8"改成"instances 的**平均** ≥ 0.8"。这是**放宽**,不是 bugfix —— 0.6 + 1.0 的一对原来不予晋升,改后会晋升。如果保留 CL v2,你可以只收"删掉重复的 Scope Decision Guide 表格"那一半,不收门槛放宽。)

### P3 — plugin 化迁移(此时再做,才不会返工)

动手写 `plugin.json` 前**先读** `/Users/d0m999/.claude/plugins/marketplaces/ecc/.claude-plugin/PLUGIN_SCHEMA_NOTES.md`。三条硬约束,违反任何一条安装直接失败:

1. **绝不能写 `agents` 字段** —— 不是合法 manifest 字段,会报 `agents: Invalid input`。`agents/*.md` 按约定自动发现。
2. **绝不能写 `hooks` 字段** —— Claude Code v2.1+ 自动加载 `hooks/hooks.json`,重复声明报 `Duplicate hooks file detected`(ECC 为此 fix/revert 过 4 次)。
3. **保留 `mcpServers: {}`** —— 这是故意留的空 opt-out,防止根目录 `.mcp.json` 被自动发现后生成超过 64 字符的 MCP 工具名。

`marketplace.json` 只声明 `{"name": "...", "source": "./"}`,即**仓库根目录本身就是 plugin**,`plugins/` 目录只是文档。

**迁移时一并做的两件事:**
- 把 `quality-gate.js` / `config-protection.js` 从"install.sh 软链 + settings.json 手工注册"改成 `hooks/hooks.json` 自动加载,**并从 settings.json 里删掉那两条**,否则双重执行。
- 定下 command 的 `agent:` 用裸名还是 `<plugin>:security-reviewer`。

### P4 — strategic-compact(单独一项,因为它对你特别相关,且必须等 P3)

你跑在 `claude-opus-4-8[1m]` 上,而上游新版正是为 1M 窗口重写的(按真实 token 用量而非工具调用次数,1M 窗口阈值 250k,靠模型名的 `[1m]` 标记自动识别,之后每涨 60k 提醒一次;新增 `COMPACT_CONTEXT_THRESHOLD` / `COMPACT_CONTEXT_INTERVAL` / `COMPACT_STATE_TTL_DAYS`)。

动作:
- vendor `scripts/hooks/suggest-compact.js`(271 行)到本仓库 `hooks/`(与 `quality-gate.js` 同级)
- **删掉 `skills/strategic-compact/suggest-compact.sh`**(54 行死文件,没有任何东西引用它)
- SKILL.md 同步上游版本
- **hook 注册放到 P3 的 `hooks.json` 里一次做完** —— 上游新版 SKILL.md 里那段"以 plugin 方式安装时不要再往 settings.json 里复制 hook 注册块,会导致 hook 双重执行"的警告,说的正是这件事

### P5 — 补能力(可与 P3 并行,因为纯加文件)

a) **Swift 六件套**(最高优先 —— 这是**唯一的能力性缺口**,前面全是修补)
b) **`conversation-analyzer` agent**(61 行、haiku、只读工具)—— 直接修好 `/hookify` 的零参数路径,那是仓库现存的已知断链
c) **`context-budget` + `config-gc` 两个 skill**(各 8K)—— 把你这次做的判断标准**工具化**:前者审计 context 消耗并按优先级给出 token 节省建议,后者对 `~/.claude` 做垃圾回收(冗余/陈旧/孤儿 skill、memory、hook、权限、MCP)。以后每季度跑一次,而不是再手工做一遍这种审计。
d) 可选:**`agent-evaluator` agent**(206 行,sonnet)—— 你有 `agent-eval` / `eval-harness` / `skill-comply` 三个 skill,却没有对应的执行体
e) 可选:**`opensource-sanitizer` agent**(197 行)—— 如果这个仓库要公开,它扫的是"发布前泄露的 secret / PII / 内部引用 / 危险文件",而现有的 `/security-scan`(扫 `.claude` 配置)和 `security-review`(扫应用代码)都不覆盖这个场景

---

## 附:两处审计维度互相矛盾,我的裁决

1. **`skills/fastapi-patterns` — 覆盖 vs 合并**:一个维度说"纯升级,可整文件覆盖",另一个说"上游删掉了本地独有内容"。**后者对**(它逐条列出了被删的内容),**裁决:合并**。取上游正文,把 CORS credentials 警告、OpenAPI 自定义章节、Security/Performance Checklist、以及指向本地确实存在的 `fastapi-reviewer` + `/fastapi-review` 的 See Also 重新贴回去。

2. **gstack 引用(`mle-reviewer` / `prompt-optimizer` 的 `/qa` → `e2e-runner`)**:一个说 SYNC,一个说 KEEP_LOCAL("上游在剥离 gstack 依赖,对你反而是能力退化")。**裁决:低优先级,倾向跟随上游。** 理由:`git log -S` 已证实那行 gstack 引用是 `cc1eed9` vendoring 时从 ECC rc.1 带进来的,**不是本地改动,不能当 LOCAL 保护**;它是仓库 `agents/` 目录里唯一的外部依赖孤点;而仓库的设计目标是零外部依赖 + Codex 兼容(`7e88a5d`),gstack 的 `/qa` 在 Codex 里不存在。同步后 agent 层完全自洽。**这不影响你在 Claude Code 会话里继续用 gstack `/qa`。** 属于"顺手改,不值得单独排期"。

3. **`agents/build-error-resolver.md` 不属于上面那一类** —— `architect` 和 `code-architect` 本地都在,不是悬空,是路由错了对象。上游是对的,收。

4. **CL v2 的 ReDoS / mktemp 严重性**:两个维度都标 high 且都说"macOS 上是硬故障"。**实测推翻**:CL v2 的 hook 在 `~/.claude/settings.json` 里一个都没注册,全部休眠。真实严重性是"仓库分发了一份带 SSRF 的死代码",而不是"你的会话随时会被卡死"。这直接把决策从"同步 8 个文件"改成了"用还是删"。