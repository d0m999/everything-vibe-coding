#!/usr/bin/env node
/**
 * PostToolUse hook: format the file that was just edited, then report any
 * lint problems back to the model.
 *
 * Runs a tool only when the project has configured it (biome.json, .prettierrc,
 * [tool.ruff], go.mod). A project that configures nothing gets nothing — this
 * hook never imposes a formatter the project did not ask for.
 *
 * Never blocks: feedback goes back as additionalContext, exit code is always 0.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

const TIMEOUT_MS = 15000;
const SKIP_DIRS = /(^|\/)(node_modules|\.venv|venv|dist|build|\.next|target|vendor|\.git)\//;

const JS_EXTS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.jsonc', '.css', '.md', '.mdx'];
const ROOT_MARKERS = ['package.json', 'pyproject.toml', 'go.mod', '.git'];

function exec(bin, args, cwd) {
  return spawnSync(bin, args, { cwd, encoding: 'utf8', timeout: TIMEOUT_MS, env: process.env });
}

function onPath(bin) {
  return spawnSync('command', ['-v', bin], { shell: true, encoding: 'utf8' }).status === 0;
}

function findRoot(dir) {
  const home = os.homedir();
  let cur = dir;
  while (cur && cur !== path.dirname(cur) && cur !== home) {
    if (ROOT_MARKERS.some((m) => fs.existsSync(path.join(cur, m)))) return cur;
    cur = path.dirname(cur);
  }
  return dir;
}

function readIfExists(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch { return ''; }
}

/** Which JS/TS formatter has this project actually configured? */
function detectJsFormatter(root) {
  const has = (f) => fs.existsSync(path.join(root, f));
  if (has('biome.json') || has('biome.jsonc')) return 'biome';

  const prettierConfigs = [
    '.prettierrc', '.prettierrc.json', '.prettierrc.js', '.prettierrc.cjs',
    '.prettierrc.yml', '.prettierrc.yaml',
    'prettier.config.js', 'prettier.config.cjs', 'prettier.config.mjs',
  ];
  if (prettierConfigs.some(has)) return 'prettier';

  try {
    const pkg = JSON.parse(readIfExists(path.join(root, 'package.json')) || '{}');
    if (pkg.prettier) return 'prettier';
  } catch { /* unparseable package.json — treat as unconfigured */ }

  return null;
}

/** Prefer the project's pinned binary over whatever happens to be on PATH. */
function resolveBin(root, name) {
  const local = path.join(root, 'node_modules', '.bin', name);
  if (fs.existsSync(local)) return local;
  return onPath(name) ? name : null;
}

function ruffConfigured(root) {
  if (fs.existsSync(path.join(root, 'ruff.toml')) || fs.existsSync(path.join(root, '.ruff.toml'))) return true;
  return readIfExists(path.join(root, 'pyproject.toml')).includes('[tool.ruff');
}

/**
 * @returns {string[]} problems worth telling the model about
 */
function check(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const root = findRoot(path.dirname(filePath));
  const notes = [];

  if (JS_EXTS.includes(ext)) {
    const formatter = detectJsFormatter(root);
    if (!formatter) return notes;

    const bin = resolveBin(root, formatter);
    if (!bin) return notes;

    if (formatter === 'biome') {
      const r = exec(bin, ['check', '--write', filePath], root);
      // Biome exits non-zero when diagnostics remain after --write (i.e. the
      // problems it cannot fix for you).
      if (r.status !== 0 && (r.stdout || r.stderr)) {
        notes.push(`Biome 在 ${path.basename(filePath)} 中仍有未自动修复的问题:\n${(r.stdout || r.stderr).trim()}`);
      }
    } else {
      exec(bin, ['--write', filePath], root);
    }
    return notes;
  }

  if (ext === '.py') {
    if (!ruffConfigured(root)) return notes;
    const bin = resolveBin(root, 'ruff');
    if (!bin) return notes;

    exec(bin, ['format', filePath], root);
    const r = exec(bin, ['check', filePath], root);
    if (r.status !== 0 && (r.stdout || r.stderr)) {
      notes.push(`Ruff 在 ${path.basename(filePath)} 中发现问题:\n${(r.stdout || r.stderr).trim()}`);
    }
    return notes;
  }

  if (ext === '.go') {
    if (!onPath('gofmt')) return notes;
    exec('gofmt', ['-w', filePath], root);
    return notes;
  }

  return notes;
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  try {
    const input = raw.trim() ? JSON.parse(raw) : {};
    const filePath = input?.tool_input?.file_path;
    if (!filePath || SKIP_DIRS.test(filePath) || !fs.existsSync(filePath)) process.exit(0);

    const notes = check(path.resolve(filePath));
    if (notes.length) {
      const body = notes.join('\n\n').slice(0, 4000);
      process.stdout.write(JSON.stringify({
        systemMessage: `质量门禁: ${path.basename(filePath)} 存在 lint 问题`,
        hookSpecificOutput: {
          hookEventName: 'PostToolUse',
          additionalContext: `[quality-gate]\n${body}`,
        },
      }));
    }
  } catch {
    // A broken hook must never break the edit that triggered it.
  }
  process.exit(0);
});
