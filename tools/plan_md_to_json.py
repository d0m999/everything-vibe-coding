"""Parse a `plan-orchestrate` Markdown output into a typed dict.

Public API
----------
parse(md_str: str) -> PlanResult
    Raise ParseError (with line/snippet context) on any structural problem.

MISSING_HANDOFF_PLACEHOLDER
    Loaded at import time from HANDOFF.schema.json (single source of truth).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Shared constant — single source of truth is HANDOFF.schema.json
# ---------------------------------------------------------------------------
_SCHEMA_PATH = Path(__file__).with_name("HANDOFF.schema.json")
_schema_data: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
MISSING_HANDOFF_PLACEHOLDER: str = _schema_data["_constants"]["MISSING_HANDOFF_PLACEHOLDER"]


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class ParseError(ValueError):
    """Raised when the Markdown cannot be parsed into a valid plan structure."""


# ---------------------------------------------------------------------------
# TypedDicts (structural contracts, usable by downstream agents)
# ---------------------------------------------------------------------------
class AgentEntry(TypedDict):
    name: str
    prompt: str


class StepEntry(TypedDict):
    id: int
    title: str
    tags: list[str]
    chain: str
    agents: list[AgentEntry]


class WaveEntry(TypedDict):
    wave: int
    steps: list[str]
    notes: str


class DepEntry(TypedDict):
    step: str
    deps: list[str]
    annotation: str


class ParallelGraph(TypedDict):
    waves: list[WaveEntry]
    deps: list[DepEntry]


class MetaBlock(TypedDict):
    plan: str
    lang: str
    py_sub: str | None
    steps_count: int
    scope: str


class PlanResult(TypedDict):
    meta: MetaBlock
    steps: list[StepEntry]
    parallel_graph: ParallelGraph


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------
_RE_PLAN = re.compile(r"^\*\*Plan\*\*:\s*`([^`]+)`", re.MULTILINE)
_RE_LANG = re.compile(
    r"^\*\*Lang\*\*:\s*`([^`]+)`(?:\s*\(py_sub:\s*`([^`]+)`\))?",
    re.MULTILINE,
)
_RE_STEPS_COUNT = re.compile(r"^\*\*Steps\*\*:\s*(\d+)", re.MULTILINE)
_RE_SCOPE = re.compile(r"^\*\*Scope\*\*:\s*(.+)$", re.MULTILINE)

# H2 step header — em-dash U+2014
_RE_STEP_H2 = re.compile(r"^## Step (\d+) — (.+)$", re.MULTILINE)

_RE_TAGS = re.compile(r"^\*\*Tags\*\*:\s*(.+)$", re.MULTILINE)
_RE_CHAIN = re.compile(r"^\*\*Chain rationale\*\*:\s*(.+)$", re.MULTILINE)

# subagent_type field inside an Agent(...) fence
_RE_SUBAGENT_TYPE = re.compile(r'^\s*subagent_type="([^"]+)"', re.MULTILINE)

# Waves table row: | int | step-... | notes |
_RE_WAVE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|", re.MULTILINE)

# Deps bullet: - step-N → deps: [...] (annotation)
_RE_DEP = re.compile(
    r"^- (step-\d+) → deps: \[([^\]]*)\] \((.+)\)$",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _require_anchor(md: str) -> int:
    """Return the char offset of '# Plan-Orchestrate Result', or raise."""
    idx = md.find("# Plan-Orchestrate Result")
    if idx == -1:
        raise ParseError(
            "Anchor '# Plan-Orchestrate Result' not found in input. "
            "Ensure the markdown starts with this heading."
        )
    return idx


def _parse_meta(body: str) -> MetaBlock:
    """Extract meta block from the region after the anchor heading."""
    m_plan = _RE_PLAN.search(body)
    if not m_plan:
        raise ParseError("Meta field '**Plan**' not found after anchor.")

    m_lang = _RE_LANG.search(body)
    if not m_lang:
        raise ParseError("Meta field '**Lang**' not found after anchor.")

    m_steps = _RE_STEPS_COUNT.search(body)
    if not m_steps:
        raise ParseError("Meta field '**Steps**' not found after anchor.")

    m_scope = _RE_SCOPE.search(body)
    if not m_scope:
        raise ParseError("Meta field '**Scope**' not found after anchor.")

    return MetaBlock(
        plan=m_plan.group(1),
        lang=m_lang.group(1),
        py_sub=m_lang.group(2) if m_lang.group(2) else None,
        steps_count=int(m_steps.group(1)),
        scope=m_scope.group(1).strip(),
    )


def _extract_agent_fences(step_text: str, step_id: int) -> list[AgentEntry]:
    """Extract all Agent(...) fences from a step block text."""
    # Split on triple-backtick fences
    # Pattern: ``` ... Agent(\n  subagent_type="...",\n  prompt="..."\n) ... ```
    fence_pattern = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
    fences = fence_pattern.findall(step_text)

    agents: list[AgentEntry] = []
    for fence_content in fences:
        # Must contain subagent_type
        m_name = _RE_SUBAGENT_TYPE.search(fence_content)
        if not m_name:
            raise ParseError(
                f"Step {step_id}: Agent fence found but missing 'subagent_type' field. "
                f"Snippet: {fence_content[:120]!r}"
            )
        name = m_name.group(1)
        prompt = _extract_prompt(fence_content, step_id)
        agents.append(AgentEntry(name=name, prompt=prompt))

    if not agents:
        raise ParseError(
            f"Step {step_id}: No Agent fences (``` ... ```) found. "
            "Each step must contain at least one Agent block."
        )

    return agents


def _extract_prompt(fence_content: str, step_id: int) -> str:
    """Extract the prompt= value, handling \\\" escapes safely via ast.literal_eval."""
    # Locate  prompt="..."  where the value may span multiple lines and contain \"
    # Strategy: find `prompt=` then grab the opening quote, then walk char-by-char.
    idx = fence_content.find('prompt=')
    if idx == -1:
        raise ParseError(
            f"Step {step_id}: Agent fence has no 'prompt=' field. "
            f"Snippet: {fence_content[:120]!r}"
        )

    # Advance past `prompt=` to the opening quote
    start = idx + len('prompt=')
    while start < len(fence_content) and fence_content[start] in (' ', '\t'):
        start += 1

    if start >= len(fence_content) or fence_content[start] not in ('"', "'"):
        raise ParseError(
            f"Step {step_id}: 'prompt=' not followed by a quoted string. "
            f"Snippet: {fence_content[idx:idx+40]!r}"
        )

    quote_char = fence_content[start]
    # Walk forward handling backslash escapes (state machine — no greedy regex)
    pos = start + 1
    chars: list[str] = []
    while pos < len(fence_content):
        ch = fence_content[pos]
        if ch == '\\' and pos + 1 < len(fence_content):
            next_ch = fence_content[pos + 1]
            if next_ch == quote_char:
                chars.append(quote_char)
                pos += 2
                continue
            if next_ch == 'n':
                chars.append('\n')
                pos += 2
                continue
            if next_ch == '\\':
                chars.append('\\')
                pos += 2
                continue
            # Other escapes: keep as-is
            chars.append(ch)
            chars.append(next_ch)
            pos += 2
            continue
        if ch == quote_char:
            break
        chars.append(ch)
        pos += 1
    else:
        raise ParseError(
            f"Step {step_id}: Unterminated prompt string starting at offset {start}."
        )

    return ''.join(chars).strip()


def _parse_steps(body: str) -> list[StepEntry]:
    """Extract all ## Step N — Title blocks from body."""
    matches = list(_RE_STEP_H2.finditer(body))
    if not matches:
        raise ParseError(
            "No '## Step N — Title' H2 blocks found. "
            "Expected at least one step section with em-dash (U+2014)."
        )

    steps: list[StepEntry] = []
    for i, m in enumerate(matches):
        step_id = int(m.group(1))
        title = m.group(2).strip()

        # Slice text from this H2 to the next H2 (or end)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        step_text = body[start:end]

        m_tags = _RE_TAGS.search(step_text)
        tags_raw = m_tags.group(1).strip() if m_tags else ""
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        m_chain = _RE_CHAIN.search(step_text)
        chain = m_chain.group(1).strip() if m_chain else ""

        agents = _extract_agent_fences(step_text, step_id)

        steps.append(
            StepEntry(
                id=step_id,
                title=title,
                tags=tags,
                chain=chain,
                agents=agents,
            )
        )

    return steps


def _parse_parallel_graph(body: str) -> ParallelGraph:
    """Extract waves table and deps bullets.

    Returns empty lists (not an error) when the section is absent — forward
    compat requirement from spec.
    """
    # Locate the section
    section_start = body.find("## Parallel execution graph")
    if section_start == -1:
        # Spec: forward compat — return empty graph, do NOT raise
        return ParallelGraph(waves=[], deps=[])

    section_text = body[section_start:]

    # --- Waves table ---
    waves: list[WaveEntry] = []
    for m in _RE_WAVE_ROW.finditer(section_text):
        wave_num = int(m.group(1))
        steps_raw = m.group(2).strip()
        notes = m.group(3).strip()
        step_list = [s.strip() for s in steps_raw.split(",") if s.strip()]
        waves.append(WaveEntry(wave=wave_num, steps=step_list, notes=notes))

    # --- Deps bullets ---
    deps: list[DepEntry] = []
    dep_section_start = section_text.find("**Dependency sources**:")
    if dep_section_start != -1:
        dep_text = section_text[dep_section_start:]
        for m in _RE_DEP.finditer(dep_text):
            step_name = m.group(1)
            deps_raw = m.group(2).strip()
            annotation = m.group(3).strip()
            dep_list = [d.strip() for d in deps_raw.split(",") if d.strip()]
            deps.append(DepEntry(step=step_name, deps=dep_list, annotation=annotation))

    return ParallelGraph(waves=waves, deps=deps)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_file(path: str | Path) -> PlanResult:
    """Read a markdown file and parse it.

    Parameters
    ----------
    path:
        Path to the ``plan-orchestrate`` output Markdown file.

    Returns
    -------
    PlanResult
        Same structure as :func:`parse`.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    UnicodeDecodeError
        If ``path`` cannot be decoded as UTF-8.
    ParseError
        If any required structural element is missing or malformed.
    """
    return parse(Path(path).read_text(encoding="utf-8"))


def parse(md_str: str) -> PlanResult:
    """Parse an orchestrate-plan Markdown string into a structured dict.

    Parameters
    ----------
    md_str:
        Full content of a ``plan-orchestrate`` output Markdown file.

    Returns
    -------
    PlanResult
        TypedDict with keys ``meta``, ``steps``, ``parallel_graph``.

    Raises
    ------
    ParseError
        If any required structural element is missing or malformed.
    """
    if not md_str or not md_str.strip():
        raise ParseError("Input is empty or blank.")

    anchor_idx = _require_anchor(md_str)
    # Work only on the text at and after the anchor
    body = md_str[anchor_idx:]

    meta = _parse_meta(body)
    steps = _parse_steps(body)
    parallel_graph = _parse_parallel_graph(body)

    return PlanResult(meta=meta, steps=steps, parallel_graph=parallel_graph)
