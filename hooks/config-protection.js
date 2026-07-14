#!/usr/bin/env node
/**
 * PreToolUse hook: block edits to linter/formatter config files.
 *
 * Agents routinely "fix" a failing check by loosening the rule instead of the
 * code. Creating a config where none exists is fine — there is nothing to
 * weaken — so only modifications to an existing file are denied.
 *
 * Escape hatch: ALLOW_CONFIG_EDIT=1
 */

'use strict';

const fs = require('fs');
const path = require('path');

const PROTECTED = new Set([
  // ESLint
  '.eslintrc', '.eslintrc.js', '.eslintrc.cjs', '.eslintrc.json',
  '.eslintrc.yml', '.eslintrc.yaml',
  'eslint.config.js', 'eslint.config.mjs', 'eslint.config.cjs',
  'eslint.config.ts', 'eslint.config.mts', 'eslint.config.cts',
  // Prettier
  '.prettierrc', '.prettierrc.js', '.prettierrc.cjs', '.prettierrc.json',
  '.prettierrc.yml', '.prettierrc.yaml',
  'prettier.config.js', 'prettier.config.cjs', 'prettier.config.mjs',
  // Biome
  'biome.json', 'biome.jsonc',
  // Python — pyproject.toml is deliberately absent: it carries project
  // metadata and dependencies alongside [tool.ruff].
  'ruff.toml', '.ruff.toml', 'setup.cfg', '.flake8', 'mypy.ini',
  // Go / shell / style / markdown
  '.golangci.yml', '.golangci.yaml', '.shellcheckrc',
  '.stylelintrc', '.stylelintrc.json', '.stylelintrc.yml',
  '.markdownlint.json', '.markdownlint.yaml', '.markdownlintrc',
]);

const DENY_REASON = (name) =>
  `禁止修改 ${name}。请改代码去满足 linter/formatter 规则，而不是放宽配置。` +
  `如果这确实是一次正当的配置变更，用 ALLOW_CONFIG_EDIT=1 重跑该命令，或临时移除 config-protection hook。`;

function allow() {
  process.exit(0);
}

function deny(name) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: DENY_REASON(name),
    },
  }));
  process.exit(0);
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  try {
    if (process.env.ALLOW_CONFIG_EDIT === '1') allow();

    const input = raw.trim() ? JSON.parse(raw) : {};
    const filePath = input?.tool_input?.file_path;
    if (!filePath) allow();

    const name = path.basename(filePath);
    if (!PROTECTED.has(name)) allow();

    // lstat, not existsSync: EACCES/EPERM must not read as "absent" and
    // silently open the gate. Only a genuine ENOENT means it is a new file.
    try {
      fs.lstatSync(filePath);
    } catch (err) {
      if (err && err.code === 'ENOENT') allow();
    }

    deny(name);
  } catch {
    allow();
  }
});
