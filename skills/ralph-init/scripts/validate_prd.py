#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ALLOWED_STORY_TYPES = {"data-fill", "code", "validation", "migration"}
REQUIRED_TOP_LEVEL = {"project", "branchName", "description", "designDocs", "userStories"}
REQUIRED_STORY_FIELDS = {
    "id",
    "title",
    "description",
    "planSection",
    "designDocRef",
    "storyType",
    "entryCount",
    "modifies",
    "creates",
    "acceptanceCriteria",
    "priority",
    "passes",
    "notes",
}


def fail(message: str, *, why: str | None = None, fix: str | None = None,
         example_valid: str | None = None, example_invalid: str | None = None) -> None:
    print(f"FAIL: {message}")
    if why:
        print(f"  Why: {why}")
    if fix:
        print(f"  Fix: {fix}")
    if example_valid:
        print(f"  Valid example: {example_valid}")
    if example_invalid:
        print(f"  Invalid example: {example_invalid}")
    sys.exit(1)


def warn(message: str) -> None:
    print(f"WARN: {message}")


def main() -> None:
    if len(sys.argv) != 2:
        fail(
            "usage: validate_prd.py <path-to-prd.json>",
            fix="pass exactly one path argument",
            example_valid="python3 validate_prd.py .ralph/prd.json",
        )

    path = Path(sys.argv[1])
    if not path.exists():
        fail(
            f"file not found: {path}",
            why="the validator cannot check a file that does not exist on disk",
            fix="create .ralph/prd.json before running this validator, or double-check the path",
        )

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        fail(
            f"invalid json: {exc}",
            why="the file must parse as a single JSON object",
            fix="run `python3 -m json.tool < .ralph/prd.json` to pinpoint the syntax error",
        )

    missing_top = REQUIRED_TOP_LEVEL - data.keys()
    if missing_top:
        fail(
            f"missing top-level keys: {sorted(missing_top)}",
            why="the harness reads these fields on every iteration",
            fix="add the missing keys; see references/output-contracts.md §.ralph/prd.json",
            example_valid='{"project": "...", "branchName": "...", "description": "...", "designDocs": [...], "userStories": [...]}',
        )

    stories = data["userStories"]
    if not isinstance(stories, list) or not stories:
        fail(
            "userStories must be a non-empty list",
            why="a PRD with zero stories has nothing for the harness to iterate over",
            fix="add at least one story; even a single `validation` story is enough to bootstrap the loop",
        )

    priorities = []
    seen_ids = set()

    for idx, story in enumerate(stories, start=1):
        missing = REQUIRED_STORY_FIELDS - story.keys()
        if missing:
            fail(
                f"story #{idx} missing keys: {sorted(missing)}",
                fix="fill every field from the required schema, even if some are empty lists or empty strings",
            )

        story_id = story["id"]
        if story_id in seen_ids:
            fail(
                f"duplicate story id: {story_id}",
                why="story ids are used as lock keys; duplicates let the harness confuse two stories",
                fix="renumber one of them (e.g. ABC-01, ABC-02, ABC-03 — contiguous and unique)",
            )
        seen_ids.add(story_id)

        story_type = story["storyType"]
        if story_type not in ALLOWED_STORY_TYPES:
            fail(
                f"{story_id} has invalid storyType: {story_type}",
                fix=f"storyType must be one of {sorted(ALLOWED_STORY_TYPES)}",
                example_valid='"storyType": "code"',
                example_invalid=f'"storyType": "{story_type}"',
            )

        priorities.append(story["priority"])

        if story["passes"] is not False:
            fail(
                f"{story_id} passes must start as false",
                why="the harness' structural diff compares before/after passes; a story that starts true has no starting signal",
                fix='set `"passes": false` for every story at init time',
                example_invalid=f'"passes": {json.dumps(story["passes"])}',
            )

        acceptance = story["acceptanceCriteria"]
        if not isinstance(acceptance, list) or len(acceptance) < 1:
            fail(
                f"{story_id} must have at least one acceptanceCriteria item",
                why="the harness cannot verify completion without a concrete criterion",
                fix='add at least one verifiable item, e.g. "tests in foo_test.py all pass"',
            )

        if story_type == "data-fill":
            if not isinstance(story["entryCount"], int) or story["entryCount"] < 0:
                fail(
                    f"{story_id} entryCount must be a non-negative integer",
                    why="data-fill stories use entryCount as the canonical batch size",
                    example_valid='"entryCount": 42',
                    example_invalid=f'"entryCount": {json.dumps(story["entryCount"])}',
                )
        elif story["entryCount"] not in (0, None):
            warn(f"{story_id} is {story_type} but entryCount is {story['entryCount']}")

        modifies = story["modifies"]
        if not isinstance(modifies, list):
            fail(f"{story_id} modifies must be a list",
                 fix='use [] for stories that modify nothing')

        creates = story["creates"]
        if not isinstance(creates, list):
            fail(f"{story_id} creates must be a list",
                 fix='use [] for stories that create nothing')

        if story_type == "code":
            has_test = any("test" in file.lower() or "__tests__" in file for file in modifies)
            if not has_test:
                warn(f"{story_id} has no obvious test file in modifies")

    expected_priorities = list(range(1, len(stories) + 1))
    if priorities != expected_priorities:
        fail(
            f"priority must be continuous from 1..n, got {priorities}",
            why="the harness picks the next story by priority; gaps or duplicates make the ordering ambiguous",
            fix="renumber priority so it runs 1, 2, 3, ... without skips, in the order you want stories executed",
            example_valid="[1, 2, 3, 4]",
            example_invalid=f"{priorities}",
        )

    print(f"OK: {path} validated ({len(stories)} stories)")


if __name__ == "__main__":
    main()
