# hooks/

Standalone hook scripts. Plain Node, zero dependencies — no plugin, no `node_modules`.

`install.sh` symlinks `hooks/*.js` into `~/.claude/hooks/`, but **never writes `settings.json`**.
A linked script is inert until you register it. Registration is the manual step below.

## Scripts

### `quality-gate.js` — PostToolUse

Formats the file that was just edited, then reports leftover lint problems back to the model.

Runs a tool **only when the project has configured it**, so it never imposes a formatter the
project did not ask for:

| Detected | Tool |
|---|---|
| `biome.json` / `biome.jsonc` | `biome check --write` |
| `.prettierrc*`, `prettier.config.*`, `package.json#prettier` | `prettier --write` |
| `[tool.ruff]` in `pyproject.toml`, or `ruff.toml` | `ruff format` + `ruff check` |
| `.go` file, `gofmt` on PATH | `gofmt -w` |

Prefers the project's pinned `node_modules/.bin/` binary over whatever is on PATH.
Never blocks: lint findings come back as `additionalContext`, exit code is always 0.

### `config-protection.js` — PreToolUse

Denies edits to linter/formatter config files (eslint, prettier, biome, ruff, stylelint,
golangci, …). Agents routinely "fix" a failing check by loosening the rule instead of the code.

- **Creating** a config file is allowed — there is nothing to weaken yet.
- `pyproject.toml` is deliberately **not** protected: it carries project metadata and
  dependencies alongside `[tool.ruff]`, so blocking it would block legitimate changes.
- Escape hatch: `ALLOW_CONFIG_EDIT=1`.

## Registration

Merge into `~/.claude/settings.json` (append to the existing arrays — do not replace them):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "node \"$HOME/.claude/hooks/config-protection.js\"", "timeout": 5 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "node \"$HOME/.claude/hooks/quality-gate.js\"", "timeout": 20, "statusMessage": "质量门禁..." }
        ]
      }
    ]
  }
}
```

Verify a hook without waiting for it to fire, by feeding it the stdin payload it will receive:

```sh
echo '{"tool_name":"Edit","tool_input":{"file_path":"/abs/path/to/biome.json"}}' \
  | node ~/.claude/hooks/config-protection.js   # → prints a deny decision
```
