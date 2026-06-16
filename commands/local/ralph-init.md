---
description: "Design and initialize a Ralph autonomous loop from plan documents. Generate .ralph/prd.json, .ralph/PROMPT.md, .ralph/progress.txt, and ralph.sh."
argument-hint: "<plan-doc-path> [plan-doc-path-2 ...] [--model sonnet|opus]"
---

# Ralph Init

根据 `$ARGUMENTS` 中提供的实施计划文档，初始化一个可运行的 Ralph loop。

目标输出：
- `.ralph/prd.json`
- `.ralph/PROMPT.md`
- `.ralph/progress.txt`
- `ralph.sh`

把这条命令当作给 Claude 的操作指令，不要写成面向用户的解释文本。

## 输入处理

1. 解析 `$ARGUMENTS`：
   - 一个或多个计划文档路径
   - 可选 `--model sonnet|opus`
2. 默认模型是 `sonnet`。
3. 如果没有有效计划文档，立即报错并停止。
4. 多个计划文档按依赖顺序统一编排到同一个 `.ralph/prd.json`。

## 上下文预算

保持主路径精简。只读取需要的参考文件，不要默认全量加载：

- 先确定命令资源目录：Claude Code 中通常是 `~/.claude/commands/ralph-init`；Codex 中通常是 `~/.codex/prompts/ralph-init`
- 始终读取 `<命令资源目录>/references/output-contracts.md`
- 始终读取 `<命令资源目录>/references/model-sizing.md`
- 在确定需要某个非 `base` 画像的详细检查项时,读取 `<命令资源目录>/references/validation-profiles.md`(下方 step 2 内联了触发条件,可据此判断)
- 仅在出现对应风险、生成结果不一致、或你需要确认历史防坑机制时读取 `<命令资源目录>/references/incidents.md`

不要把 incident 复盘、项目特定框架检查、输出字段细则全部塞回主命令。

## 执行流程

### 1. 读取并抽取计划

对每个计划文档提取：
- 工作项、阶段、stories、tasks
- 涉及文件和目录
- 依赖关系
- 可验证的验收条件
- 文档中显式声称的数字

将每个 story 归类为：
- `data-fill`
- `code`
- `validation`
- `migration`

### 2. 先判定项目画像，再决定读哪些检查规则

不要默认执行前端专用检查。按实际计划内容和代码库形态,决定启用哪些 profile:

| Profile | 触发条件 | 是否必读 `validation-profiles.md` |
|---------|---------|----------------------------------|
| `base` | 所有项目都要 | 否,下面执行流程已覆盖 |
| `data` | 存在数据文件数量声明、批量补全、迁移、条目计数 | 是,读 `## data` section |
| `frontend-code` | story 涉及前端交互、i18n、mock、store、design token | 是,读 `## frontend-code` section |
| `backend-code` | story 涉及 API、auth、route、schema、migration、输入校验 | 是,读 `## backend-code` section |

如果只是初始化 loop 或计划基本不涉及代码框架,只执行 `base`,不要读 `validation-profiles.md`,也不要做 `frontend-code` / `backend-code` 的扩展检查。

### 3. 验证计划文档中的关键事实

只验证和当前计划真正相关的事实：
- 对数字声明，用代码或脚本验证
- 对“已有目录 / 已有 API / 已有调用点 / 已有 mock”这类描述，用实际搜索确认
- 对框架模式，不要从计划文档复制到输出文件

如果计划文档数字与真实结果不一致：
- 以验证结果为准
- 在最终报告中明确列出偏差

### 4. 拆分并排序 stories

按 `references/model-sizing.md` 的规则做模型感知拆分：
- 默认按 `sonnet` 保守拆分
- `opus` 允许更大的单 story 范围，但仍优先保持验收条件独立
- 宁可拆细，不要把多个独立交互、mock 重写、i18n 新增与消费混到一个 story

排序原则：
- 前置依赖先做
- 共享类型/工具先于消费方
- mock / schema / i18n key 准备先于依赖它们的 story
- 多计划时先排被依赖的计划

### 5. 生成四个文件

按 `references/output-contracts.md` 生成：
- `.ralph/prd.json`
- `.ralph/PROMPT.md`
- `.ralph/progress.txt`
- `ralph.sh`

要求：
- `PROMPT.md` 是操作手册，不是模板；禁止 `{...}` 占位符；必须包含反作弊段（`unequivocally true` + `do not output a false` / `do not lie`）
- `progress.txt` 的 `Codebase Patterns` 只能写实际验证过的事实
- `ralph.sh` 必须包含 story lock、结构化 diff、VIOLATION 停机、信号校验和 macOS 兼容调用方式
- `ralph.sh` 还必须包含：实例锁（`.ralph/.instance` + `kill -0` + `trap ... EXIT`）、状态文件原子写入（`.tmp.$$` + `mv`）、数值守卫 helper（`assert_nonneg_int` 或等价 `=~ ^[0-9]+$`）

### 6. 运行确定性校验脚本

生成完成后必须运行：

```bash
python3 "<命令资源目录>/scripts/validate_prd.py" .ralph/prd.json
python3 "<命令资源目录>/scripts/validate_prompt.py" .ralph/PROMPT.md
python3 "<命令资源目录>/scripts/validate_ralph.py" ralph.sh
```

若任一脚本失败:
- 修复生成结果
- 重新运行校验
- 最多重试 3 次。仍失败则停止,在最终报告里如实列出哪个脚本、哪条断言未通过,以及你尝试过的修复
- 不要带着未如实报告的失败结果结束

如果校验失败原因与历史事故高度一致,再去读 `references/incidents.md` 的对应章节。

维护者注:修改任一 validator 后,运行 `bash "<命令资源目录>/scripts/run_fixtures.sh"` 做回归,它会对 `scripts/fixtures/valid` 和 `scripts/fixtures/invalid` 下的 17 个样例逐一断言通过/失败。

## 输出要求

完成后向用户报告：
- 生成了哪些文件
- story 总数与类型分布
- 目标模型与拆分策略
- 计划文档数字和实际验证结果的偏差
- 你启用了哪些条件检查画像
- 三个校验脚本是否全部通过

若仍有未解决风险，只报告真实剩余风险，不要泛泛而谈。
