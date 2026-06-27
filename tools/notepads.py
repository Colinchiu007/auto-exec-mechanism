#!/usr/bin/env python3
"""
Wisdom Accumulation — 智慧积累 Notepad 系统
============================================
Inspired by oh-my-openagent's wisdom accumulation concept.

Manages structured .plan/notepads/ directory with auto-extraction hooks.
Four notepad files track different dimensions of accumulated knowledge:

  learnings.md      — What the agent learned (patterns, insights, gotchas)
  decisions.md      — Key decisions with rationale (why, alternatives considered)
  issues.md         — Blockers, bugs, and open issues
  verification.md   — What was verified and how (test results, manual checks)

Usage:
  python notepads.py create                               # Initialize directory structure
  python notepads.py add <notepad> <note>                 # Append a note
  python notepads.py add <notepad> --stdin                # Read note from stdin
  python notepads.py list                                 # List all notes
  python notepads.py show <notepad>                       # Show a notepad
  python notepads.py extract <plan_dir>                   # Auto-extract from context
  python notepads.py hook <task_result>                   # Post-task extraction hook

Notepad names: learnings, decisions, issues, verification
"""

import argparse
import json
import os
import sys
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "/sessions/zen-awesome-gauss/mnt/projects")
NOTEPADS_DIR = os.path.join(PROJECTS_ROOT, ".plan", "notepads")

NOTEPAD_INFO = {
    "learnings": {
        "title": "学习记录",
        "desc": "执行过程中发现的新知识、模式、陷阱和经验",
        "fmt": "- [{date}] {note}",
    },
    "decisions": {
        "title": "决策日志",
        "desc": "关键决策及其理由（为什么选A不选B）",
        "fmt": "- [{date}] **{note}**  — 原因: ",
    },
    "issues": {
        "title": "问题跟踪",
        "desc": "阻塞项、Bug 和未解决的问题",
        "fmt": "- [{date}] {note}  — 状态: open",
    },
    "verification": {
        "title": "验证记录",
        "desc": "验证了什么、如何验证、结果如何",
        "fmt": "- [{date}] **{note}**  — 方法: ",
    },
}


# ── Core Operations ─────────────────────────────────────────────────────


def notepad_path(name: str) -> str:
    return os.path.join(NOTEPADS_DIR, f"{name}.md")


def ensure_notepads():
    os.makedirs(NOTEPADS_DIR, exist_ok=True)
    for name, info in NOTEPAD_INFO.items():
        path = notepad_path(name)
        if not os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    f"# {info['title']}\n\n"
                    f"> {info['desc']}\n\n"
                    f"_初始化于 {datetime.now().isoformat()[:10]}_\n\n"
                )


def cmd_create():
    """Initialize the notepads directory."""
    ensure_notepads()
    for name, info in NOTEPAD_INFO.items():
        path = notepad_path(name)
        with open(path) as f:
            lines = f.readlines()
        print(f"  ✓ {name}.md — {len(lines)} lines", file=sys.stderr)
    print(f"\n  Notepads initialized at {NOTEPADS_DIR}", file=sys.stderr)


def cmd_add(name: str, note: str | None, stdin: bool = False):
    """Append a note to a notepad."""
    if name not in NOTEPAD_INFO:
        print(f"Error: unknown notepad '{name}'. Valid: {', '.join(NOTEPAD_INFO.keys())}", file=sys.stderr)
        sys.exit(2)

    if not note and stdin:
        note = sys.stdin.read().strip()
    if not note:
        print("Error: empty note", file=sys.stderr)
        sys.exit(2)

    ensure_notepads()
    path = notepad_path(name)
    date = datetime.now().isoformat()[:10]

    if name == "decisions":
        # decisions format: reason after —
        lines = note.split(" — ", 1)
        entry = f"- [{date}] **{lines[0]}**"
        if len(lines) > 1:
            entry += f"  — {lines[1]}"
    elif name == "verification":
        lines = note.split(" — ", 1)
        entry = f"- [{date}] **{lines[0]}**"
        if len(lines) > 1:
            entry += f"  — 方法: {lines[1]}"
    elif name == "issues":
        entry = f"- [{date}] {note}  — 状态: open"
    else:
        entry = f"- [{date}] {note}"

    with open(path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

    print(f"  ✓ {name}.md: note added", file=sys.stderr)


def cmd_list():
    """List all notepads with summary."""
    ensure_notepads()
    for name, info in NOTEPAD_INFO.items():
        path = notepad_path(name)
        with open(path) as f:
            content = f.read()
        note_count = content.count("\n- [")
        print(f"  {name}.md — {note_count} notes ({info['title']})", file=sys.stderr)


def cmd_show(name: str):
    """Show a notepad's full content."""
    if name not in NOTEPAD_INFO:
        print(f"Error: unknown notepad '{name}'", file=sys.stderr)
        sys.exit(2)
    path = notepad_path(name)
    if not os.path.isfile(path):
        print(f"  (empty)", file=sys.stderr)
        return
    with open(path) as f:
        print(f.read())


# ── Auto-extraction ─────────────────────────────────────────────────────

# Extraction patterns: heuristics to read from a task's context/output
EXTRACTION_PATTERNS = {
    "learnings": [
        "learned that", "discovered", "found that", "turns out",
        "gotcha", "important to note", "key insight",
    ],
    "decisions": [
        "decided to", "chose to", "opted for", "went with",
        "decision:", "trade-off",
    ],
    "issues": [
        "TODO:", "FIXME:", "HACK:", "bug:", "issue:",
        "blocked by", "doesn't work", "fails when",
    ],
    "verification": [
        "verified that", "confirmed", "tested", "passed",
        "✅", "all green", "pytest", "works correctly",
    ],
}


def cmd_extract(source_text: str):
    """Auto-extract notes from a text (e.g., progress.md, task output).

    Scans for keywords and proposes notes to each notepad.
    Outputs proposed additions to stderr; actual writes to stdout.
    """
    ensure_notepads()
    source_lower = source_text.lower()
    proposals = {}

    for notepad, patterns in EXTRACTION_PATTERNS.items():
        matches = []
        for pattern in patterns:
            if pattern.lower() in source_lower:
                # Find the actual line containing the match
                for line in source_text.split("\n"):
                    if pattern.lower() in line.lower():
                        line = line.strip()
                        if line and line not in matches:
                            matches.append(line[:120])
        if matches:
            proposals[notepad] = matches[:5]  # Max 5 per notepad

    if not proposals:
        print("  No extractable content found.", file=sys.stderr)
        return

    print(f"  Found {sum(len(v) for v in proposals.values())} extractable notes", file=sys.stderr)
    for notepad, notes in proposals.items():
        for note in notes:
            cmd_add(notepad, f"[auto-extract] {note}")


# ── Post-task Hook ─────────────────────────────────────────────────────

def cmd_hook(task_result_path: str):
    """Post-task extraction hook.

    Reads a task result file (JSON or text) and auto-extracts
    learnings, decisions, issues, and verification entries.
    """
    if not os.path.isfile(task_result_path):
        print(f"Error: file not found — {task_result_path}", file=sys.stderr)
        sys.exit(2)

    with open(task_result_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Try parsing as JSON first
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            text = "\n".join(
                json.dumps(item, ensure_ascii=False) for item in data
            )
        else:
            text = content
    except (json.JSONDecodeError, ValueError):
        text = content

    print(f"  Extracting from {task_result_path}", file=sys.stderr)
    cmd_extract(text)


# ── CLI ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Wisdom Accumulation Notepad System")
    sub = parser.add_subparsers(dest="command")

    # create
    sub.add_parser("create", help="Initialize notepads directory")

    # add
    add_p = sub.add_parser("add", help="Add a note to a notepad")
    add_p.add_argument("notepad", choices=list(NOTEPAD_INFO.keys()), help="Notepad name")
    add_p.add_argument("note", nargs="?", help="Note content")
    add_p.add_argument("--stdin", action="store_true", help="Read note from stdin")

    # list
    sub.add_parser("list", help="List all notepads")

    # show
    show_p = sub.add_parser("show", help="Show a notepad's content")
    show_p.add_argument("notepad", choices=list(NOTEPAD_INFO.keys()), nargs="?", default="all", help="Notepad name (default: all)")

    # extract
    extract_p = sub.add_parser("extract", help="Auto-extract notes from text")
    extract_p.add_argument("source", help="Source text or file path")

    # hook
    hook_p = sub.add_parser("hook", help="Post-task extraction hook")
    hook_p.add_argument("task_result", help="Path to task result file")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create()
    elif args.command == "add":
        cmd_add(args.notepad, args.note, args.stdin)
    elif args.command == "list":
        cmd_list()
    elif args.command == "show":
        if args.notepad == "all":
            for name in NOTEPAD_INFO:
                print(f"\n{'=' * 40}", file=sys.stderr)
                print(f"  {name}.md", file=sys.stderr)
                print(f"{'=' * 40}", file=sys.stderr)
                cmd_show(name)
        else:
            cmd_show(args.notepad)
    elif args.command == "extract":
        # If source is a file path, read it; otherwise treat as raw text
        if os.path.isfile(args.source):
            with open(args.source, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        else:
            text = args.source
        cmd_extract(text)
    elif args.command == "hook":
        cmd_hook(args.task_result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()