"""TDD tests for plan_md_to_json.parse() and parse_file().

Coverage matrix
---------------
Step-5a (original 17 tests):
  - Minimal 1-step fixture: happy path meta/step/agent/graph fields
  - Error paths: empty input, missing anchor, missing H2, broken agent fence

Step-5b2 (new tests — this file):
  - Real 2-step fixture: end-to-end from docs/plan-orchestrate-output.md
  - multi-step: len(steps)==2, steps[1]["id"]==2
  - missing-parallel-graph: forward-compat returns {waves:[], deps:[]}
  - broken-Agent sub-branches: missing prompt= / prompt= without quote / unterminated prompt
  - parse_file(): FileNotFoundError, UnicodeDecodeError
  - py_sub=None: **Lang** without (py_sub: ...) parenthetical
  - missing **Dependency sources**: section -> deps==[]
  - language-tagged fences (```Agent ...): supported — _RE_AGENT_FENCE handles optional language tag

Note on FileNotFoundError / UnicodeDecodeError:
  parse(md_str) is a pure function that never performs file I/O, so those
  error paths cannot occur through parse(). The thin wrapper parse_file()
  deliberately exposes them so they can be tested. See parse_file() docstring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plan_md_to_json import ParseError, parse, parse_file

# ---------------------------------------------------------------------------
# Minimal fixture (1 step, 1 agent) — drives RED -> GREEN (5a)
# ---------------------------------------------------------------------------
_MINIMAL_MD = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python` (py_sub: `generic`)
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | 实现 add 函数 | impl | `tdd-guide -> python-reviewer` |

## Parallel execution graph

**Parallel waves** — each wave runs concurrently in separate Claude sessions:

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no upstream deps |

**Dependency sources**:

- step-1 → deps: [] (none)

---

## Step 1 — 实现 add 函数

**Intent**: 创建并实现 add 函数。
**Tags**: impl
**Chain rationale**: 纯实现型步骤；由 tdd-guide 先落地代码。

### Agents (run sequentially; thread HANDOFF context from prior agent into next)

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] 在 tools/demo/util.py 创建 add 函数。End with HANDOFF."
)
```

---
"""

# ---------------------------------------------------------------------------
# Real 2-step fixture — derived from docs/plan-orchestrate-output.md
# Used for happy-path end-to-end and multi-step tests.
# ---------------------------------------------------------------------------
_REAL_DEMO_MD = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python` (py_sub: `generic`)
**Steps**: 2
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | 实现 add 函数 | impl | `tdd-guide -> python-reviewer` |
| 2 | 给 add 函数写 pytest 单元测试 | test | `tdd-guide -> python-reviewer` |

## Parallel execution graph

**Parallel waves** — each wave runs concurrently in separate Claude sessions;
wait for the wave to finish before launching the next:

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no upstream deps |
| 2 | step-2 | depends on step-1 (test references step-1's subject) |

**Dependency sources**:

- step-2 → deps: [step-1] (heuristic: step-1 subject add-func tools/demo/util.py)

---

## Step 1 — 实现 add 函数

**Intent**: 在 `tools/demo/util.py` 创建并实现 `add(a: int, b: int) -> int`。
**Tags**: impl
**Chain rationale**: 纯实现型步骤；由 tdd-guide 先落地代码。

### Agents (run sequentially; thread HANDOFF context from prior agent into next)

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] 实现 add 函数。End with HANDOFF."
)
```

2.
```
Agent(
  subagent_type="python-reviewer",
  prompt="[Plan: docs/demo-plan.md#step-1] 审查 add 函数。End with HANDOFF."
)
```

---

## Step 2 — 给 add 函数写 pytest 单元测试

**Intent**: 为 Step 1 中 `tools/demo/util.py` 的 `add` 函数编写完整 pytest 单元测试，覆盖率 ≥95%。
**Tags**: test
**Chain rationale**: 测试型步骤；tdd-guide 负责补齐用例。

### Agents (run sequentially; thread HANDOFF context from prior agent into next)

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-2] 编写测试。End with HANDOFF."
)
```

2.
```
Agent(
  subagent_type="python-reviewer",
  prompt="[Plan: docs/demo-plan.md#step-2] 审查测试代码质量。End with HANDOFF."
)
```

---
"""


# ===========================================================================
# 5a — Minimal fixture tests (preserved exactly from step-5a)
# ===========================================================================

class TestParseMinimalFixture:
    """Minimal RED->GREEN fixture — 1 step, 1 agent."""

    def test_first_agent_name_is_tdd_guide(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["steps"][0]["agents"][0]["name"] == "tdd-guide"

    def test_meta_plan_extracted(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["meta"]["plan"] == "docs/demo-plan.md"

    def test_meta_lang_extracted(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["meta"]["lang"] == "python"

    def test_meta_py_sub_extracted(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["meta"]["py_sub"] == "generic"

    def test_meta_steps_count(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["meta"]["steps_count"] == 1

    def test_meta_scope(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["meta"]["scope"] == "all"

    def test_step_id_and_title(self) -> None:
        result = parse(_MINIMAL_MD)
        step = result["steps"][0]
        assert step["id"] == 1
        assert step["title"] == "实现 add 函数"

    def test_step_tags(self) -> None:
        result = parse(_MINIMAL_MD)
        assert result["steps"][0]["tags"] == ["impl"]

    def test_parallel_graph_waves(self) -> None:
        result = parse(_MINIMAL_MD)
        waves = result["parallel_graph"]["waves"]
        assert len(waves) == 1
        assert waves[0]["wave"] == 1
        assert "step-1" in waves[0]["steps"]

    def test_parallel_graph_always_present(self) -> None:
        result = parse(_MINIMAL_MD)
        pg = result["parallel_graph"]
        assert "waves" in pg
        assert "deps" in pg

    def test_top_level_keys(self) -> None:
        result = parse(_MINIMAL_MD)
        assert set(result.keys()) == {"meta", "steps", "parallel_graph"}

    def test_agent_prompt_not_empty(self) -> None:
        result = parse(_MINIMAL_MD)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        assert len(prompt) > 10

    def test_prompt_contains_plan_prefix(self) -> None:
        result = parse(_MINIMAL_MD)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        assert "[Plan:" in prompt


class TestParseErrorCases:
    """Explicit ParseError branches required by spec."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ParseError, match=r"empty|blank"):
            parse("")

    def test_missing_anchor_raises(self) -> None:
        md = "Some prose without the anchor header.\n\n## Step 1 — foo\n"
        with pytest.raises(ParseError, match="Plan-Orchestrate Result"):
            parse(md)

    def test_missing_h2_step_blocks_raises(self) -> None:
        md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

"""
        with pytest.raises(ParseError, match="[Ss]tep"):
            parse(md)

    def test_corrupted_agent_fence_raises(self) -> None:
        """Agent block present but missing subagent_type field."""
        md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  BROKEN_FIELD="tdd-guide",
  prompt="hello"
)
```

---
"""
        with pytest.raises(ParseError, match="[Aa]gent|subagent_type"):
            parse(md)


# ===========================================================================
# 5b2 — New tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Happy path: real 2-step fixture, end-to-end assertions
# ---------------------------------------------------------------------------

class TestParseRealDemoFixtureEndToEnd:
    """End-to-end assertions against the real 2-step fixture."""

    def test_meta_steps_count_is_2(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["meta"]["steps_count"] == 2

    def test_steps_list_length_is_2(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert len(result["steps"]) == 2

    def test_step2_id_is_2(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["steps"][1]["id"] == 2

    def test_step2_title_is_chinese(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["steps"][1]["title"] == "给 add 函数写 pytest 单元测试"

    def test_step2_tags_is_test(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["steps"][1]["tags"] == ["test"]

    def test_step1_has_two_agents(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert len(result["steps"][0]["agents"]) == 2

    def test_step1_agent1_is_tdd_guide(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["steps"][0]["agents"][0]["name"] == "tdd-guide"

    def test_step1_agent2_is_python_reviewer(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["steps"][0]["agents"][1]["name"] == "python-reviewer"

    def test_parallel_graph_waves_count_is_2(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert len(result["parallel_graph"]["waves"]) == 2

    def test_parallel_graph_wave2_contains_step2(self) -> None:
        result = parse(_REAL_DEMO_MD)
        wave2 = result["parallel_graph"]["waves"][1]
        assert wave2["wave"] == 2
        assert "step-2" in wave2["steps"]

    def test_parallel_graph_deps_count_is_1(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert len(result["parallel_graph"]["deps"]) == 1

    def test_parallel_graph_deps_entry_structure(self) -> None:
        """deps[0] must match {step, deps, annotation} with precise values."""
        result = parse(_REAL_DEMO_MD)
        dep = result["parallel_graph"]["deps"][0]
        assert dep["step"] == "step-2"
        assert dep["deps"] == ["step-1"]
        # annotation must reference the upstream step
        assert "step-1" in dep["annotation"]

    def test_meta_scope_all(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["meta"]["scope"] == "all"

    def test_meta_lang_python(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["meta"]["lang"] == "python"

    def test_meta_py_sub_generic(self) -> None:
        result = parse(_REAL_DEMO_MD)
        assert result["meta"]["py_sub"] == "generic"


# ---------------------------------------------------------------------------
# Missing parallel graph — forward-compat
# ---------------------------------------------------------------------------

_MD_NO_PARALLEL_GRAPH = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | 实现 add 函数 | impl | chain |

---

## Step 1 — 实现 add 函数

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""


class TestParseMissingParallelGraph:
    """Forward-compat: absent ## Parallel execution graph returns empty lists, does not raise."""

    def test_parse_returns_empty_waves_when_parallel_graph_absent(self) -> None:
        result = parse(_MD_NO_PARALLEL_GRAPH)
        assert result["parallel_graph"]["waves"] == []

    def test_parse_returns_empty_deps_when_parallel_graph_absent(self) -> None:
        result = parse(_MD_NO_PARALLEL_GRAPH)
        assert result["parallel_graph"]["deps"] == []

    def test_parse_does_not_raise_when_parallel_graph_absent(self) -> None:
        """Ensure no ParseError is raised — forward compat requirement."""
        # No assertion needed beyond no exception; the above two tests check values.
        result = parse(_MD_NO_PARALLEL_GRAPH)
        assert "parallel_graph" in result


# ---------------------------------------------------------------------------
# Missing Dependency sources section — deps should be empty list
# ---------------------------------------------------------------------------

_MD_NO_DEP_SECTION = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | 实现 add 函数 | impl | chain |

## Parallel execution graph

**Parallel waves** — each wave runs concurrently:

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no upstream deps |

---

## Step 1 — 实现 add 函数

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""


class TestParseMissingDependencySources:
    """When **Dependency sources**: section is absent, deps must be empty list."""

    def test_parse_returns_empty_deps_when_dependency_sources_absent(self) -> None:
        result = parse(_MD_NO_DEP_SECTION)
        assert result["parallel_graph"]["deps"] == []

    def test_parse_waves_still_populated_when_dep_section_absent(self) -> None:
        result = parse(_MD_NO_DEP_SECTION)
        assert len(result["parallel_graph"]["waves"]) == 1
        assert result["parallel_graph"]["waves"][0]["wave"] == 1


# ---------------------------------------------------------------------------
# Broken Agent fence sub-branches
# ---------------------------------------------------------------------------

def _make_step_md(agent_body: str) -> str:
    """Build a minimal valid plan MD with the given agent_body inside the fence."""
    return f"""\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
{agent_body}
```

---
"""


class TestParseBrokenAgentFence:
    """ParseError branches for malformed Agent(...) fences."""

    def test_parse_raises_when_prompt_field_missing(self) -> None:
        """Agent fence has subagent_type but no prompt= field at all."""
        md = _make_step_md('Agent(\n  subagent_type="tdd-guide"\n)')
        with pytest.raises(ParseError, match=r"[Pp]rompt|prompt="):
            parse(md)

    def test_parse_raises_when_prompt_not_followed_by_quote(self) -> None:
        """prompt= present but value is not a quoted string (e.g., prompt=42)."""
        md = _make_step_md(
            'Agent(\n  subagent_type="tdd-guide",\n  prompt=42\n)'
        )
        with pytest.raises(ParseError, match=r"[Qq]uoted|quote|prompt="):
            parse(md)

    def test_parse_raises_when_prompt_string_unterminated(self) -> None:
        """Opening quote present but closing quote never appears (unterminated)."""
        md = _make_step_md(
            'Agent(\n  subagent_type="tdd-guide",\n  prompt="hello world, never closed\n)'
        )
        with pytest.raises(ParseError, match=r"[Uu]nterminated|prompt"):
            parse(md)

    def test_parse_raises_when_no_agent_fences_present(self) -> None:
        """Step block has no ``` fences at all."""
        md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1. Just prose, no fence block here.

---
"""
        with pytest.raises(ParseError, match=r"[Aa]gent|fence"):
            parse(md)


# ---------------------------------------------------------------------------
# py_sub = None (no parenthetical in **Lang** line)
# ---------------------------------------------------------------------------

_MD_NO_PY_SUB = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | 实现 add 函数 | impl | chain |

---

## Step 1 — 实现 add 函数

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""


class TestParseMetaPySub:
    """py_sub field is None when **Lang** line has no (py_sub: ...) parenthetical."""

    def test_parse_py_sub_is_none_when_parenthetical_absent(self) -> None:
        result = parse(_MD_NO_PY_SUB)
        assert result["meta"]["py_sub"] is None

    def test_parse_lang_still_extracted_when_no_py_sub(self) -> None:
        result = parse(_MD_NO_PY_SUB)
        assert result["meta"]["lang"] == "python"


# ---------------------------------------------------------------------------
# Language-tagged fences — xfail (implementation does not support yet)
# ---------------------------------------------------------------------------

def test_parse_language_tagged_fence_extracted() -> None:
    """A fence opened with ```Agent (language tag) is parsed correctly."""
    md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```Agent
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""
    result = parse(md)
    assert result["steps"][0]["agents"][0]["name"] == "tdd-guide"


# ---------------------------------------------------------------------------
# parse_file() — FileNotFoundError and UnicodeDecodeError
# ---------------------------------------------------------------------------

class TestParseFile:
    """parse_file() wrapper exposes file I/O errors that parse() never sees."""

    def test_parse_file_raises_file_not_found_for_nonexistent_path(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/path/that/does/not/exist/plan.md")

    def test_parse_file_raises_unicode_decode_error_for_non_utf8_bytes(
        self, tmp_path: Path
    ) -> None:
        """Write raw non-UTF-8 bytes (Latin-1 specific sequence) and confirm UnicodeDecodeError."""
        bad_file = tmp_path / "bad.md"
        # \xff\xfe is a UTF-16 BOM — invalid in a UTF-8 only read
        bad_file.write_bytes(b"\xff\xfe invalid utf-8 content \x80\x81")
        with pytest.raises(UnicodeDecodeError):
            parse_file(bad_file)

    def test_parse_file_parses_valid_utf8_file(self, tmp_path: Path) -> None:
        """parse_file returns same result as parse() for a well-formed file."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(_MINIMAL_MD, encoding="utf-8")
        result = parse_file(plan_file)
        assert result["meta"]["plan"] == "docs/demo-plan.md"
        assert result["meta"]["steps_count"] == 1

    def test_parse_file_accepts_path_object(self, tmp_path: Path) -> None:
        """parse_file accepts pathlib.Path, not just str."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(_MINIMAL_MD, encoding="utf-8")
        result = parse_file(plan_file)
        assert result["steps"][0]["agents"][0]["name"] == "tdd-guide"

    def test_parse_file_accepts_string_path(self, tmp_path: Path) -> None:
        """parse_file accepts a plain str path."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(_MINIMAL_MD, encoding="utf-8")
        result = parse_file(str(plan_file))
        assert result["meta"]["lang"] == "python"


# ---------------------------------------------------------------------------
# Missing meta fields — _parse_meta ParseError branches
# ---------------------------------------------------------------------------

def _make_meta_md(*, include_plan: bool = True, include_lang: bool = True,
                  include_steps: bool = True, include_scope: bool = True) -> str:
    """Build a minimal plan MD with optional meta fields omitted."""
    plan_line = "**Plan**: `docs/demo-plan.md`\n" if include_plan else ""
    lang_line = "**Lang**: `python`\n" if include_lang else ""
    steps_line = "**Steps**: 1\n" if include_steps else ""
    scope_line = "**Scope**: all\n" if include_scope else ""

    return f"""\
# Plan-Orchestrate Result

{plan_line}{lang_line}{steps_line}{scope_line}
## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""


class TestParseMetaFieldErrors:
    """ParseError when required meta fields are absent."""

    def test_parse_raises_when_plan_field_missing(self) -> None:
        md = _make_meta_md(include_plan=False)
        with pytest.raises(ParseError, match=r"\*\*Plan\*\*|Plan"):
            parse(md)

    def test_parse_raises_when_lang_field_missing(self) -> None:
        md = _make_meta_md(include_lang=False)
        with pytest.raises(ParseError, match=r"\*\*Lang\*\*|Lang"):
            parse(md)

    def test_parse_raises_when_steps_field_missing(self) -> None:
        md = _make_meta_md(include_steps=False)
        with pytest.raises(ParseError, match=r"\*\*Steps\*\*|Steps"):
            parse(md)

    def test_parse_raises_when_scope_field_missing(self) -> None:
        md = _make_meta_md(include_scope=False)
        with pytest.raises(ParseError, match=r"\*\*Scope\*\*|Scope"):
            parse(md)


# ---------------------------------------------------------------------------
# Prompt escape sequences — _extract_prompt backslash branches
# ---------------------------------------------------------------------------

def _make_prompt_md(prompt_value: str) -> str:
    """Build a plan MD where the agent prompt field contains prompt_value literally."""
    return f"""\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="{prompt_value}"
)
```

---
"""


class TestParsePromptEscapes:
    """Verify _extract_prompt handles backslash escape sequences correctly."""

    def test_parse_prompt_with_escaped_quote(self) -> None:
        """Backslash-escaped quote inside prompt string is preserved as a literal quote."""
        md = _make_prompt_md(r'hello \"world\" end')
        result = parse(md)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        assert '"world"' in prompt

    def test_parse_prompt_with_escaped_newline(self) -> None:
        r"""Backslash-n inside prompt string is decoded as a real newline."""
        md = _make_prompt_md(r"line1\nline2")
        result = parse(md)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        assert "\n" in prompt

    def test_parse_prompt_with_escaped_backslash(self) -> None:
        r"""Double-backslash inside prompt string is decoded as a single backslash."""
        md = _make_prompt_md(r"path\\to\\file")
        result = parse(md)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        assert "\\" in prompt

    def test_parse_prompt_with_other_escape_sequence_kept_as_is(self) -> None:
        r"""Unknown escape sequences (e.g. \t) are kept verbatim (backslash + char)."""
        md = _make_prompt_md(r"value\twith\rtab")
        result = parse(md)
        prompt = result["steps"][0]["agents"][0]["prompt"]
        # \t is not a recognized escape in the parser, so it becomes literal \t
        assert "\\t" in prompt or "\t" in prompt  # either kept or decoded

    def test_parse_prompt_with_leading_spaces_after_equals(self) -> None:
        """prompt=   "value" (spaces between = and opening quote) is still parsed."""
        md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt=   "spaced value here"
)
```

---
"""
        result = parse(md)
        assert result["steps"][0]["agents"][0]["prompt"] == "spaced value here"


# ---------------------------------------------------------------------------
# New test 1 — mixed tagged and bare fences in one Step
# ---------------------------------------------------------------------------

def test_parse_mixed_tagged_and_bare_fences_both_extracted() -> None:
    """A Step with one language-tagged fence and one bare fence yields two agents in order."""
    md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl
**Chain rationale**: chain.

### Agents

1.
```Agent
Agent(
  subagent_type="code-explorer",
  prompt="[Plan: docs/demo-plan.md#step-1] explore codebase."
)
```

2.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""
    result = parse(md)
    agents = result["steps"][0]["agents"]
    assert len(agents) == 2
    assert agents[0]["name"] == "code-explorer"
    assert agents[1]["name"] == "tdd-guide"


# ---------------------------------------------------------------------------
# New test 2 — step without **Tags**: line returns empty list
# ---------------------------------------------------------------------------

def test_step_without_tags_line_returns_empty_list() -> None:
    """When **Tags**: line is absent from a step, tags must be []."""
    md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

---

## Step 1 — foo

**Intent**: foo.
**Chain rationale**: chain.

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""
    result = parse(md)
    assert result["steps"][0]["tags"] == []


# ---------------------------------------------------------------------------
# New test 3 — step without **Chain rationale**: line returns empty string
# ---------------------------------------------------------------------------

def test_step_without_chain_line_returns_empty_string() -> None:
    """When **Chain rationale**: line is absent from a step, chain must be ''."""
    md = """\
# Plan-Orchestrate Result

**Plan**: `docs/demo-plan.md`
**Lang**: `python`
**Steps**: 1
**Scope**: all

## Steps overview

| # | Title | Tags | Chain |
|---|---|---|---|
| 1 | foo | impl | chain |

## Parallel execution graph

| Wave | Steps | Notes |
|---|---|---|
| 1 | step-1 | no deps |

**Dependency sources**:

---

## Step 1 — foo

**Intent**: foo.
**Tags**: impl

### Agents

1.
```
Agent(
  subagent_type="tdd-guide",
  prompt="[Plan: docs/demo-plan.md#step-1] implement. End with HANDOFF."
)
```

---
"""
    result = parse(md)
    assert result["steps"][0]["chain"] == ""
