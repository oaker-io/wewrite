#!/usr/bin/env python3
"""
Learn from human edits by diffing AI draft vs published final.

Compares the original AI-generated article with the human-edited version,
categorizes the changes, and saves lessons to lessons/.

When 5+ lessons accumulate, outputs a prompt for the Agent to update playbook.md.

Usage:
    python3 learn_edits.py --draft path/to/draft.md --final path/to/final.md
    python3 learn_edits.py --summarize   # summarize all lessons

The script does structural analysis; the Agent (LLM) interprets the diffs
and writes the lesson YAML + playbook updates.
"""

import argparse
import difflib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).parent.parent


def load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def split_sections(text: str) -> list[dict]:
    """Split markdown into sections by H2 headers."""
    sections = []
    current = {"header": "(intro)", "lines": []}

    for line in text.split("\n"):
        if line.strip().startswith("## "):
            if current["lines"] or current["header"] != "(intro)":
                sections.append(current)
            current = {"header": line.strip(), "lines": []}
        else:
            current["lines"].append(line)

    sections.append(current)
    return sections


def extract_title(text: str) -> str:
    for line in text.split("\n"):
        if line.strip().startswith("# ") and not line.strip().startswith("## "):
            return line.strip()[2:].strip()
    return ""


def compute_diff(draft: str, final: str) -> dict:
    """Compute structured diff between draft and final."""
    draft_lines = draft.split("\n")
    final_lines = final.split("\n")

    # Line-level diff
    differ = difflib.unified_diff(draft_lines, final_lines, lineterm="")
    diff_lines = list(differ)

    # Categorize changes
    additions = []
    deletions = []
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            deletions.append(line[1:].strip())

    # Filter empty lines
    additions = [l for l in additions if l]
    deletions = [l for l in deletions if l]

    # Title change
    draft_title = extract_title(draft)
    final_title = extract_title(final)
    title_changed = draft_title != final_title

    # Section-level analysis
    draft_sections = split_sections(draft)
    final_sections = split_sections(final)
    draft_h2s = [s["header"] for s in draft_sections if s["header"] != "(intro)"]
    final_h2s = [s["header"] for s in final_sections if s["header"] != "(intro)"]
    structure_changed = draft_h2s != final_h2s

    # Word count change
    draft_chars = len(draft.replace("\n", "").replace(" ", ""))
    final_chars = len(final.replace("\n", "").replace(" ", ""))

    return {
        "title_changed": title_changed,
        "draft_title": draft_title,
        "final_title": final_title,
        "structure_changed": structure_changed,
        "draft_h2s": draft_h2s,
        "final_h2s": final_h2s,
        "lines_added": len(additions),
        "lines_deleted": len(deletions),
        "draft_chars": draft_chars,
        "final_chars": final_chars,
        "char_diff": final_chars - draft_chars,
        "additions_sample": additions[:20],
        "deletions_sample": deletions[:20],
    }


def save_diff_for_analysis(diff_result: dict, draft_path: str, final_path: str):
    """Save diff data for Agent to analyze and write lessons."""
    lessons_dir = SKILL_DIR / "lessons"
    lessons_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    diff_file = lessons_dir / f"{date_str}-diff.yaml"

    # If file exists, append a counter
    counter = 1
    while diff_file.exists():
        diff_file = lessons_dir / f"{date_str}-diff-{counter}.yaml"
        counter += 1

    data = {
        "date": date_str,
        "draft_file": str(draft_path),
        "final_file": str(final_path),
        "diff_summary": {
            "title_changed": diff_result["title_changed"],
            "draft_title": diff_result["draft_title"],
            "final_title": diff_result["final_title"],
            "structure_changed": diff_result["structure_changed"],
            "lines_added": diff_result["lines_added"],
            "lines_deleted": diff_result["lines_deleted"],
            "char_diff": diff_result["char_diff"],
        },
        "edits": [],  # Agent fills this after analysis
        "patterns": [],  # Agent fills this after analysis
    }

    with open(diff_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    return diff_file


def count_lessons() -> int:
    """Count existing lesson files."""
    lessons_dir = SKILL_DIR / "lessons"
    if not lessons_dir.exists():
        return 0
    return len(list(lessons_dir.glob("*-diff*.yaml")))


def summarize_lessons():
    """Load all lessons and output for Agent to update playbook."""
    lessons_dir = SKILL_DIR / "lessons"
    if not lessons_dir.exists():
        print("No lessons directory found.")
        return

    lesson_files = sorted(lessons_dir.glob("*-diff*.yaml"))
    if not lesson_files:
        print("No lessons found.")
        return

    all_lessons = []
    for f in lesson_files:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            if data:
                all_lessons.append(data)

    print(f"Total lessons: {len(all_lessons)}")
    print(json.dumps(all_lessons, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Learn from human edits")
    parser.add_argument("--draft", help="Path to AI draft")
    parser.add_argument("--final", help="Path to human-edited final")
    parser.add_argument("--summarize", action="store_true", help="Summarize all lessons")
    args = parser.parse_args()

    if args.summarize:
        summarize_lessons()
        return

    if not args.draft or not args.final:
        print("Error: --draft and --final required", file=sys.stderr)
        sys.exit(1)

    # Load texts
    draft = load_text(args.draft)
    final = load_text(args.final)

    # Compute diff
    diff_result = compute_diff(draft, final)

    # Print summary
    print("=" * 60)
    print("EDIT ANALYSIS")
    print("=" * 60)

    if diff_result["title_changed"]:
        print(f"\n标题修改:")
        print(f"  AI:   {diff_result['draft_title']}")
        print(f"  人工: {diff_result['final_title']}")

    if diff_result["structure_changed"]:
        print(f"\n结构修改:")
        print(f"  AI H2:   {diff_result['draft_h2s']}")
        print(f"  人工 H2: {diff_result['final_h2s']}")

    print(f"\n数量变化:")
    print(f"  新增 {diff_result['lines_added']} 行, 删除 {diff_result['lines_deleted']} 行")
    print(f"  字数变化: {diff_result['char_diff']:+d} ({diff_result['draft_chars']} → {diff_result['final_chars']})")

    if diff_result["deletions_sample"]:
        print(f"\n被删除的内容（采样）:")
        for line in diff_result["deletions_sample"][:10]:
            print(f"  - {line[:80]}")

    if diff_result["additions_sample"]:
        print(f"\n新增的内容（采样）:")
        for line in diff_result["additions_sample"][:10]:
            print(f"  + {line[:80]}")

    # Save for Agent analysis
    diff_file = save_diff_for_analysis(diff_result, args.draft, args.final)
    print(f"\nDiff saved to: {diff_file}")

    # Check if playbook update should be triggered
    lesson_count = count_lessons()
    print(f"Total lessons: {lesson_count}")

    if lesson_count >= 5 and lesson_count % 5 == 0:
        print(f"\n{'='*60}")
        print("PLAYBOOK UPDATE TRIGGERED")
        print(f"{'='*60}")
        print(f"{lesson_count} lessons accumulated. Agent should:")
        print(f"1. Read all lessons: python3 learn_edits.py --summarize")
        print(f"2. Read current playbook: playbook.md")
        print(f"3. Update playbook with recurring patterns from lessons")

    # Output instructions for Agent
    print(f"""
{'='*60}
INSTRUCTIONS FOR AGENT
{'='*60}

Read the draft and final versions, then analyze the edits:

1. Read: {args.draft}
2. Read: {args.final}
3. For each meaningful edit, classify it:
   - type: "用词替换" / "段落删除" / "段落新增" / "结构调整" / "标题修改" / "语气调整"
   - before: (original text)
   - after: (edited text)
   - pattern: (what this tells us about the user's preference)

4. Update {diff_file} with the edits and patterns lists.

5. If this is a recurring pattern (seen in previous lessons too),
   consider updating playbook.md.
""")


if __name__ == "__main__":
    main()
