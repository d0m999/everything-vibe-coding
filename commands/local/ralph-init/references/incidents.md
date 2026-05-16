# Incidents

只在出现相同风险、或生成结果与校验脚本不一致时读取本文件。

## 1. 单轮吃掉所有 stories

症状：
- agent 在一次 iteration 内连续完成多个 story

根因：
- 只靠自然语言说“每轮处理一个 story”，没有技术边界

防护：
- story lock
- 结构化 diff
- `VIOLATION` 停机
- `COMPLETE` 交叉验证

## 2. `PROMPT.md` 被当成模板

症状：
- `{story}`、`{pattern}`、`{model}` 原样出现在最终 prompt 中

根因：
- `PROMPT.md` 通过 stdin 直接传给 Claude，不会做模板替换

防护：
- `PROMPT.md` 只能写“从哪里读取什么”
- 校验脚本禁止模板变量

## 3. 模型能力和 story 尺寸不匹配

症状：
- 单个 story 涉及太多文件、交互或上下文切换，导致 agent 反复失败

防护：
- 按模型做 story sizing
- 默认按 `sonnet` 保守拆分

## 4. 框架模式抄错

症状：
- i18n、store、mock、route 写成计划文档声称的模式，而不是项目真实模式

防护：
- 先选 validation profile
- 只对相关画像执行真实代码验证

## 5. grep / 校验模式误匹配

症状：
- 验收条件里的搜索模式命中 `test(`、`it(`、`import(`) 等无关内容

防护：
- 用更精确的 regex
- 生成后跑确定性校验脚本

## 6. macOS 不兼容 CLI

症状：
- `timeout: command not found`
- `claude -p` 导致行为不符预期

防护：
- 使用 `claude --print --dangerously-skip-permissions --model ...`
- 不使用 `timeout`

## 7. 错误处理吞故障

症状：
- `|| true`、`|| echo 0` 掩盖真实失败

防护：
- 保留退出码
- 区分 hard fail、crash、warning

## 8. ralph 提交到错误分支

症状：
- ralph commit 出现在 feature branch 而非 main
- 后续迭代的 prd.json 与 main 不同步，导致 VIOLATION 停机

根因：
- 用户在 feature branch 上启动 `ralph.sh`，harness 没有检查/切换分支
- PROMPT.md 中写"先 checkout main"无效：agent 可能忽略，linter/hook 可能还原
- 循环内 `git stash && checkout main && stash pop` 方案也无效：stash pop 把 feature branch 的 dirty files 带入 main 工作区，污染状态

防护（最终方案）：
- `ralph.sh` 启动前做 hard gate：必须在 main 且工作区干净，否则 `exit 1`
- 循环内每轮做 assert：若不在 main 则 `break` 停机（防止 agent 偷切分支）
- **不要在循环内做 stash/checkout** —— 这是已验证失败的方案

## 9. prd.json 跨分支不同步触发 VIOLATION

症状：
- harness 报 `VIOLATION:changed=[P5-03,...,P5-08],locked=P5-08`
- agent 只处理了锁定 story，但 harness 检测到多个 story 的 passes 状态变化

根因：
- P5-03~P5-07 在 main 上已 passes=true，但当前分支 prd.json 仍是 false
- agent 读 progress.txt 发现已完成的 story 状态不一致，擅自修正 → VIOLATION

防护：
- harness 每轮切到正确分支后 prd.json 自然同步
- 若需多分支运行 ralph，必须在启动前显式同步 prd.json：`git checkout main -- .ralph/prd.json`

## 10. `declare -A` macOS bash 3.x 不兼容

症状：
- `declare: -A: invalid option`，ralph.sh 直接退出

根因：
- macOS 自带 `/bin/bash` 是 3.x，不支持关联数组

防护：
- 用文件版 retry tracker：`$RALPH_DIR/.retries/<story_id>` 存计数
- 不依赖 bash 4+ 特性

## 11. `progress.txt` 写入想当然结论

症状：
- `Codebase Patterns` 中出现未经验证的目录、函数、框架模式

防护：
- 只写实证结果
- 不存在的目录标为“新建”
