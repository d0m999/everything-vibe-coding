<!-- Source: ecc@2.0.0-rc.1, vendored on 2026-05-16 from commands/hookify-list.md -->
---
description: List all configured hookify rules
---

Find and display all hookify rules in a formatted table.

## Steps

1. Find all `.claude/hookify.*.local.md` files
2. Read each file's frontmatter:
   - `name`
   - `enabled`
   - `event`
   - `action`
   - `pattern`
3. Display them as a table:

| Rule | Enabled | Event | Pattern | File |
|------|---------|-------|---------|------|

4. Show the rule count and remind the user that `/hookify-configure` can change state later.
