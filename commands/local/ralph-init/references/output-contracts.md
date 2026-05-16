# Output Contracts

只在生成四个输出文件时读取本文件。

## `.ralph/prd.json`

顶层字段：
- `project`
- `branchName`
- `description`
- `designDocs`
- `userStories`

每个 story 至少包含：
- `id`
- `title`
- `description`
- `planSection`
- `designDocRef`
- `storyType`
- `entryCount`
- `modifies`
- `creates`
- `acceptanceCriteria`
- `priority`
- `passes`
- `notes`

规则：
- `id` 使用统一前缀和连续编号，例如 `ABC-01`
- `priority` 从 `1` 开始连续递增
- 初始 `passes` 必须全部为 `false`
- `storyType` 仅允许 `data-fill|code|validation|migration`
- `data-fill` 的 `entryCount` 用实际验证值；其他类型默认 `0`
- `modifies` 宁多勿少，`code` story 应包含对应测试文件
- `acceptanceCriteria` 必须可验证，避免“界面正常”“体验良好”之类主观表述
- `notes` 只写执行编排、风险和兼容策略，不要塞冗长背景

## `.ralph/PROMPT.md`

这是 Ralph agent 的操作手册，不是模板文件。

必须包含：
- 步骤 0：读取 `.ralph/current_story.json`
- 读取 `.ralph/progress.txt`，优先看 `## Codebase Patterns`
- 读取 `.ralph/prd.json` 中锁定的 story
- 按 storyType 执行 PLAN / EXECUTE / VERIFY / REPORT
- 步骤 F：更新状态、写回 `progress.txt`、提交 git commit
- 步骤 G：输出 `<promise>YIELD</promise>` 或 `<promise>COMPLETE</promise>` 并立即停止
- **Completion integrity 段**：显式告诉 agent `<promise>COMPLETE</promise>` 必须 `unequivocally true`，`do not output a false promise`，`do not lie` 来逃出循环；阻塞时必须写入 `progress.txt` 并改输出 `YIELD`

硬约束：
- 禁止 `{story}`、`{model}`、`{pattern}` 之类模板变量
- 所有动态值都写成"从哪个文件读取哪个字段"
- 必须明确"禁止处理锁定 story 之外的任何 story"
- 必须说明 harness 会做结构化 diff 和违规停机
- 必须包含反作弊关键短语：`unequivocally true`（或 `genuinely true`）**和** `do not output a false` / `do not lie` —— validator 会逐字 grep

## `.ralph/progress.txt`

必须预填 `## Codebase Patterns` 区段。

只写真实验证过的事实，至少包含与当前项目相关的内容：
- 测试命令
- 关键目录结构
- 导入别名
- 数据文件结构和已验证条目数
- 编辑约束
- 已确认的框架模式
- 关键函数或入口点
- 跨 story 一致性规则

条件内容：
- 只有前端 story 时才写 i18n / mock / store / design token
- 只有后端 story 时才写 route / auth / schema / migration
- 不存在的目录要标成“新建”，不要写成“已有”

## `ralph.sh`

如果项目根目录没有 `ralph.sh`，生成标准模板。
如果已有 `ralph.sh`，补齐缺失机制，不要破坏已有正确逻辑。

必须包含：
- story lock 写入 `.ralph/current_story.json`
- 迭代前后的 `prd.json` 状态快照
- 只允许锁定 story 的 `passes` 从 `false` 变为 `true`
- 违规时 `VIOLATION` 停机
- `<promise>COMPLETE</promise>` 与实际 prd 状态交叉验证
- `claude --print --dangerously-skip-permissions --model ... < "$PROMPT_FILE"`
- 显式记录 `CLAUDE_EXIT_CODE`
- 检查 `YIELD|COMPLETE` 信号
- 每轮清理 story lock
- macOS 兼容：不要用 `timeout`，不要用 `claude -p`，不要用 `declare -A`（bash 3.x 无关联数组，用文件版 tracker 替代）
- 启动前 hard gate：必须在目标分支且工作区干净，否则 `exit 1`（不要用循环内 stash/checkout，已验证失败）
- 循环内每轮 assert 仍在目标分支，若 agent 偷切则 `break` 停机
- retry tracker 用文件而非 shell 变量：`$RALPH_DIR/.retries/<story_id>` 存计数
- **实例锁** `.ralph/.instance`：写入 `$$:$(date +%s)`，启动时用 `kill -0` 检测同名 PID 是否仍存活，存活则拒绝覆盖；`trap 'rm -f ...' EXIT` 退出时清理
- **状态文件原子写入**：向 `.ralph/current_story.json` 等 state 文件写入时必须通过 `*.tmp.$$` 临时文件 + `mv` 覆盖，不允许直接 `>` 写目标文件（防半写状态）
- **数值守卫 helper**：定义 `assert_nonneg_int()`（或等价 `[[ "$x" =~ ^[0-9]+$ ]]` 校验），所有从文件/退出码/状态读出的数值在参与算术或条件判断前必须先过它

## 生成后必做

执行：

```bash
python3 ~/.claude/commands/ralph-init/scripts/validate_prd.py .ralph/prd.json
python3 ~/.claude/commands/ralph-init/scripts/validate_prompt.py .ralph/PROMPT.md
python3 ~/.claude/commands/ralph-init/scripts/validate_ralph.py ralph.sh
```

任何失败都必须先修复，再汇报结果。
