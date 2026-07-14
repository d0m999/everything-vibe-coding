# CLAUDE.md

本仓库的操作契约（不含通用编码规范，那些在 `~/.claude/rules/`）。

## 规则

1. 任何 `skills/` `commands/` `agents/` `hooks/` 下的新增、删除或 attic 之后，**必须**依次跑：

   ```bash
   ./install.sh --apply --prune
   ./scripts/generate-codex-command-skills.sh && ./install-codex.sh --apply --prune
   ./scripts/doctor.sh
   ```

   并把 `doctor.sh` 的输出贴出来。

2. 修改任何 vendored 文件（frontmatter 闭合 `---` 之后有 `<!-- Source: ecc@... -->` 注释的），
   **必须**在 `docs/LOCAL-PATCHES.md` 追加一行。

3. **绝不** `cp` / `ln` 任何东西进 `~/.claude/` 或 `~/.codex/`；安装的唯一入口是
   `install.sh` 和 `install-codex.sh` 两个脚本。

4. 计数、预算类数字不要手抄进 README 或其他文档，一律引用脚本输出
   （`check-references.sh`、`doctor.sh` 等）。

## 维护流程

```
vendor
  → ./scripts/check-references.sh
  → ./install.sh --apply --prune
  → ./scripts/generate-codex-command-skills.sh && ./install-codex.sh --apply --prune
  → ./scripts/doctor.sh          # 二值门禁，必须为 0
```
