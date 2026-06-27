#!/usr/bin/env python3
"""
planning-cli — .plan/ 状态管理 CLI

基于 GSD Core 的 state CLI 设计理念，提供结构化状态读写能力。

用法:
  python planning_cli.py state get                    # 人读状态
  python planning_cli.py state get --json             # JSON 输出
  python planning_cli.py state get <section>          # 指定字段
  python planning_cli.py state update <field> <value> # 更新标量字段
  python planning_cli.py state patch --key1 val1      # 批量更新
  python planning_cli.py state add-decision --summary "..." [--rationale "..."]
  python planning_cli.py state add-blocker --text "..."
  python planning_cli.py state resolve-blocker --id <N>
  python planning_cli.py plan index                   # 任务清单索引
  python planning_cli.py plan advance                 # 推进计划编号
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "/sessions/zen-awesome-gauss/mnt/projects")
PLAN_DIR = os.path.join(PROJECTS_ROOT, ".plan")

STATE_TEMPLATE = """---
version: {version}
goal: "{goal}"
scope: "{scope}"
status: {status}
created: "{created}"
updated: "{updated}"
metrics:
  total_plans: {total_plans}
  completed_plans: {completed_plans}
  failed_plans: {failed_plans}
  blocked_plans: {blocked_plans}
  phase: {phase}
  started_at: {started_at_null}
  completed_at: {completed_at_null}
decisions: []
blockers: []
current_plan: null
---
"""


def _empty_state() -> dict:
    now = datetime.now(timezone.utc).isoformat()[:19]
    return {
        "version": 1,
        "goal": "",
        "scope": "",
        "status": "planning",
        "created": now,
        "updated": now,
        "metrics": {
            "total_plans": 0,
            "completed_plans": 0,
            "failed_plans": 0,
            "blocked_plans": 0,
            "phase": None,
            "started_at": None,
            "completed_at": None,
        },
        "decisions": [],
        "blockers": [],
        "current_plan": None,
    }


# ── YAML frontmatter parser (no deps) ──────────────────────────────

_YAML_SCALAR = re.compile(r'^(\w[\w_]*):\s*(.*?)\s*$')
_NULL_VALUES = {"null", "none", "~", ""}


def _parse_frontmatter(text: str) -> tuple[dict, str, int]:
    """Parse YAML frontmatter (--- ... ---) from markdown text.

    Returns (parsed_dict, body_text, line_count).
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return _empty_state(), text, len(lines)

    end = 1
    while end < len(lines) and lines[end].strip() != "---":
        end += 1

    if end >= len(lines):
        return _empty_state(), text, len(lines)

    raw = lines[1:end]
    body = "\n".join(lines[end + 1:])

    state = _empty_state()

    # Stack of (indent, dict) — track nesting
    indent_stack: list[tuple[int, dict]] = [(0, state)]

    # Current list item being populated (None if not inside a list item)
    current_item: dict | None = None
    last_list_item_indent = -1

    line_idx = 0

    while line_idx < len(raw):
        stripped = raw[line_idx].rstrip()
        line_idx += 1
        if not stripped.strip():
            continue

        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()

        # Pop stack to correct indent level
        while len(indent_stack) > 1 and indent <= indent_stack[-1][0]:
            indent_stack.pop()

        parent = indent_stack[-1][1]

        # -- List item --
        if content.startswith("- "):
            item_text = content[2:]
            m = _YAML_SCALAR.match(item_text)
            if m:
                entry = {m.group(1): _parse_yaml_value(m.group(2))}
                # Find the list this item belongs to
                # The list should be the parent at this indent level
                current_item = entry
                last_list_item_indent = indent

                # Find or create the list in parent
                # Walk back to find the key that has a list
                list_found = False
                for potential_list_key, potential_list_val in list(parent.items()):
                    if isinstance(potential_list_val, list):
                        potential_list_val.append(entry)
                        list_found = True
                        break

                if not list_found:
                    # Create new list
                    if indent > 0:
                        for k, v in list(parent.items()):
                            if v is None:
                                nl = [entry]
                                parent[k] = nl
                                list_found = True
                                break
                    if not list_found:
                        # Last resort: collect under a default key
                        pass
            else:
                current_item = None
                val = _parse_yaml_value(item_text)
                # Find the list
                for potential_list_val in parent.values():
                    if isinstance(potential_list_val, list):
                        potential_list_val.append(val)
                        break
            continue

        # -- Non-list key --
        # If we are inside a list item and this line is indented more than
        # the list item (indent > last_list_item_indent), add to current item
        if current_item is not None and indent > last_list_item_indent:
            target = current_item
        else:
            target = parent
            current_item = None

        m = _YAML_SCALAR.match(content)
        if not m:
            continue

        key, raw_val = m.group(1), m.group(2)

        if raw_val and raw_val not in _NULL_VALUES:
            target[key] = _parse_yaml_value(raw_val)
        else:
            # May be null or start of nested structure
            if line_idx < len(raw):
                next_line = raw[line_idx]
                next_indent = len(next_line) - len(next_line.lstrip())
                next_stripped = next_line.strip()

                if next_indent > indent:
                    if next_stripped.startswith("- "):
                        new_list: list = []
                        target[key] = new_list
                    else:
                        new_dict: dict = {}
                        target[key] = new_dict
                        indent_stack.append((indent, new_dict))
                else:
                    target[key] = None
            else:
                target[key] = None

    return state, body, len(lines)



def _parse_yaml_value(raw: str):
    """Parse scalar YAML value."""
    v = raw.strip()
    if not v or v.lower() in _NULL_VALUES:
        return None
    if v.startswith("[") and v.endswith("]"):
        # Inline YAML array — return as empty list for [] case
        inner = v[1:-1].strip()
        if not inner:
            return []
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _serialize_yaml_value(val) -> str:

    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        # Escape internal quotes
        if '"' in val:
            return f"'{val}'"
        return f'"{val}"'
    return str(val)


def _build_frontmatter(state: dict) -> str:
    """Serialize state dict back to YAML frontmatter."""
    lines = ["---"]
    for key, val in state.items():
        if key in ("decisions", "blockers"):
            if not val:
                continue
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - id: {item.get('id', 0)}")
                for k, v in item.items():
                    if k == "id":
                        continue
                    lines.append(f"    {k}: {_serialize_yaml_value(v)}")
            continue
        if isinstance(val, dict):
            lines.append(f"{key}:")
            for k2, v2 in val.items():
                null_key = f"{k2}_null" if k2.endswith("_at") else None
                # Handle None values for *_at fields
                if v2 is None:
                    null_key = k2
                    lines.append(f"  {k2}: null")
                else:
                    lines.append(f"  {k2}: {_serialize_yaml_value(v2)}")
            continue
        lines.append(f"{key}: {_serialize_yaml_value(val)}")
    lines.append("---")
    lines.append("")  # blank line before body
    return "\n".join(lines)


# ── IO ─────────────────────────────────────────────────────────────

# State is stored as .plan/state.json (machine source of truth).
# STATE.md is a human-readable view generated on write.

def _json_path() -> str:
    return os.path.join(PLAN_DIR, "state.json")


def _state_path() -> str:
    return os.path.join(PLAN_DIR, "STATE.md")


def read_state() -> dict:
    path = _json_path()
    if not os.path.isfile(path):
        return _empty_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_state()


def write_state(state: dict, body: str = ""):
    os.makedirs(PLAN_DIR, exist_ok=True)
    state["updated"] = datetime.now(timezone.utc).isoformat()[:19]

    # Write machine-readable JSON
    with open(_json_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)

    # Write human-readable STATE.md
    fm = _build_frontmatter(state)
    md_body = body or _build_state_body(state)
    with open(_state_path(), "w", encoding="utf-8") as f:
        f.write(fm + ("\n" + md_body if md_body else ""))


def _build_state_body(state: dict) -> str:
    """Build human-readable body for STATE.md."""
    lines = ["", "## Current State", ""]
    lines.append(f"- Goal: {state.get('goal', '')}")
    lines.append(f"- Status: {state.get('status', '')}")
    m = state.get("metrics", {})
    lines.append(f"- Plans: {m.get('total_plans', 0)} total, {m.get('completed_plans', 0)} done")
    decs = state.get("decisions", [])
    if decs:
        lines.append("")
        lines.append("## Decisions")
        for d in decs[-5:]:
            lines.append(f"- #{d.get('id', '?')}: {d.get('summary', '')[:60]}")
    blks = state.get("blockers", [])
    open_blk = [b for b in blks if b.get("status") == "open"]
    if open_blk:
        lines.append("")
        lines.append("## Blockers")
        for b in open_blk:
            lines.append(f"- #{b.get('id', '?')}: {b.get('text', '')[:60]}")
    return "\n".join(lines)


def _touch_state(state: dict | None = None):
    if state is None:
        state = _empty_state()
    write_state(state)
    return state


# ── Commands ───────────────────────────────────────────────────────


def cmd_state_get(args: argparse.Namespace) -> int:
    state = read_state()
    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.section:
        keys = args.section.split(".")
        val = state
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, {})
            else:
                print(f"error: key '{args.section}' not found", file=sys.stderr)
                return 1
        print(json.dumps(val, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"goal:      {state.get('goal', '')}")
    print(f"scope:     {state.get('scope', '')}")
    print(f"status:    {state.get('status', 'planning')}")
    print(f"created:   {state.get('created', '')}")
    print(f"updated:   {state.get('updated', '')}")
    m = state.get("metrics", {})
    print(f"plans:     {m.get('total_plans', 0)} total, {m.get('completed_plans', 0)} done, "
          f"{m.get('failed_plans', 0)} failed, {m.get('blocked_plans', 0)} blocked")
    if state.get("current_plan"):
        print(f"current:   plan #{state['current_plan']}")
    decisions = state.get("decisions", [])
    if decisions:
        print(f"\ndecisions ({len(decisions)}):")
        for d in decisions[-3:]:  # last 3
            print(f"  #{d.get('id', '?')} {d.get('summary', '')[:60]}")
    blockers = state.get("blockers", [])
    open_blockers = [b for b in (blockers or []) if b.get("status") == "open"]
    if open_blockers:
        print(f"\nblockers ({len(open_blockers)} open):")
        for b in open_blockers:
            print(f"  #{b.get('id', '?')} {b.get('text', '')[:60]}")
    return 0


def cmd_state_update(args: argparse.Namespace) -> int:
    state = read_state()
    key = args.field
    val = args.value

    # Handle nested keys with dot notation
    if "." in key:
        parts = key.split(".")
        target = state
        for p in parts[:-1]:
            if p not in target:
                target[p] = {}
            target = target[p]
        target[parts[-1]] = _parse_yaml_value(val)
    else:
        state[key] = _parse_yaml_value(val)

    write_state(state)
    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"✓ {key} = {val}")
    return 0


def cmd_state_patch(args: argparse.Namespace) -> int:
    state = read_state()
    pairs = getattr(args, "pairs", [])
    for pair in pairs:
        if "=" not in pair:
            print(f"warning: skipping '{pair}' (expected key=value)", file=sys.stderr)
            continue
        k, v = pair.split("=", 1)
        if "." in k:
            parts = k.split(".")
            target = state
            for p in parts[:-1]:
                if p not in target:
                    target[p] = {}
                target = target[p]
            target[parts[-1]] = _parse_yaml_value(v)
        else:
            state[k] = _parse_yaml_value(v)
    write_state(state)
    print(f"✓ patched {len(pairs)} field(s)")
    return 0


def _next_id(items: list[dict]) -> int:
    return max((item.get("id", 0) for item in items), default=0) + 1


def cmd_state_add_decision(args: argparse.Namespace) -> int:
    state = read_state()
    now = datetime.now(timezone.utc).isoformat()[:19]
    entry = {
        "id": _next_id(state.get("decisions", [])),
        "summary": args.summary,
        "rationale": args.rationale or "",
        "timestamp": now,
    }
    state.setdefault("decisions", []).append(entry)
    write_state(state)
    print(f"✓ decision #{entry['id']} added")
    return 0


def cmd_state_add_blocker(args: argparse.Namespace) -> int:
    state = read_state()
    now = datetime.now(timezone.utc).isoformat()[:19]
    entry = {
        "id": _next_id(state.get("blockers", [])),
        "text": args.text,
        "status": "open",
        "created": now,
        "resolved": None,
    }
    state.setdefault("blockers", []).append(entry)
    write_state(state)
    print(f"✓ blocker #{entry['id']} added")
    return 0


def cmd_state_resolve_blocker(args: argparse.Namespace) -> int:
    state = read_state()
    now = datetime.now(timezone.utc).isoformat()[:19]
    for b in state.get("blockers", []):
        if b.get("id") == args.id:
            b["status"] = "resolved"
            b["resolved"] = now
            write_state(state)
            print(f"✓ blocker #{args.id} resolved")
            return 0
    print(f"error: blocker #{args.id} not found", file=sys.stderr)
    return 1


def cmd_plan_index(args: argparse.Namespace) -> int:
    """List tasks from task_plan.md."""
    tp = os.path.join(PLAN_DIR, "task_plan.md")
    if not os.path.isfile(tp):
        print("no task_plan.md found", file=sys.stderr)
        return 1
    with open(tp, "r", encoding="utf-8") as f:
        text = f.read()

    # Parse markdown table rows
    in_table = False
    tasks = []
    for line in text.split("\n"):
        if line.strip().startswith("|") and not in_table:
            in_table = True
            continue
        if in_table and line.strip().startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 9 and cells[0].isdigit():
                tasks.append({
                    "id": int(cells[0]),
                    "task": cells[1],
                    "role": cells[2],
                    "deps": cells[3],
                    "risk": cells[4],
                    "prd": cells[5],
                    "status": cells[7],
                })
        if in_table and not line.strip().startswith("|"):
            in_table = False

    if args.json:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        return 0

    if not tasks:
        print("no tasks found in task_plan.md", file=sys.stderr)
        return 0

    for t in tasks:
        status_icon = {"completed": "✓", "in_progress": "▶", "failed": "✗",
                       "blocked": "⊘", "pending": "○"}.get(t["status"], "○")
        print(f"  {status_icon} #{t['id']} [{t['role']}] {t['task'][:60]}")
    return 0


def cmd_plan_advance(args: argparse.Namespace) -> int:
    """Advance plan/phase counter."""
    state = read_state()
    current = state.get("current_plan") or 0
    state["current_plan"] = current + 1
    write_state(state)
    print(f"✓ advanced to plan #{state['current_plan']}")
    return 0


# ── Init ───────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize STATE.md with defaults."""
    s = _empty_state()
    if args.goal:
        s["goal"] = args.goal
    if args.scope:
        s["scope"] = args.scope
    _touch_state(s)
    print(f"✓ STATE.md initialized at {_state_path()}")
    return 0


# ── Main ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description=".plan/ 状态管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  state get [--json] [<section>]   Read state
  state update <field> <value>      Update scalar field
  state patch -- <key=val> ...      Batch update
  state add-decision --summary ...   Record decision
  state add-blocker --text ...       Add blocker
  state resolve-blocker --id <N>     Resolve blocker
  plan index [--json]               List tasks from task_plan.md
  plan advance                       Bump plan counter
  init --goal "..." [--scope "..."]  Initialize STATE.md
        """,
    )
    parser.add_argument("--plan-dir", "-p", default=None, help=".plan/ directory (default: PROJECTS_ROOT/.plan)")

    sub = parser.add_subparsers(dest="command")

    # state get
    sg = sub.add_parser("state")
    sg_sub = sg.add_subparsers(dest="state_cmd")

    sg_get = sg_sub.add_parser("get", help="Dump state")
    sg_get.add_argument("section", nargs="?", default=None, help="Key path (e.g. metrics.total_plans)")
    sg_get.add_argument("--json", action="store_true", help="JSON output")
    sg_get.set_defaults(func=cmd_state_get)

    sg_upd = sg_sub.add_parser("update", help="Update scalar field")
    sg_upd.add_argument("field", help="Field name (dot notation supported)")
    sg_upd.add_argument("value", help="New value")
    sg_upd.add_argument("--json", action="store_true", help="JSON output")
    sg_upd.set_defaults(func=cmd_state_update)

    sg_patch = sg_sub.add_parser("patch", help="Batch update")
    sg_patch.add_argument("pairs", nargs="+", metavar="key=val", help="Field=value pairs")
    sg_patch.set_defaults(func=cmd_state_patch)

    sg_dec = sg_sub.add_parser("add-decision", help="Add decision")
    sg_dec.add_argument("--summary", required=True)
    sg_dec.add_argument("--rationale", default="")
    sg_dec.set_defaults(func=cmd_state_add_decision)

    sg_blk = sg_sub.add_parser("add-blocker", help="Add blocker")
    sg_blk.add_argument("--text", required=True)
    sg_blk.set_defaults(func=cmd_state_add_blocker)

    sg_res = sg_sub.add_parser("resolve-blocker", help="Resolve blocker")
    sg_res.add_argument("--id", type=int, required=True)
    sg_res.set_defaults(func=cmd_state_resolve_blocker)

    # state level fallback
    sg.set_defaults(func=lambda a: parser.print_help())

    # plan
    pg = sub.add_parser("plan")
    pg_sub = pg.add_subparsers(dest="plan_cmd")

    pg_idx = pg_sub.add_parser("index", help="List tasks")
    pg_idx.add_argument("--json", action="store_true")
    pg_idx.set_defaults(func=cmd_plan_index)

    pg_adv = pg_sub.add_parser("advance", help="Advance plan counter")
    pg_adv.set_defaults(func=cmd_plan_advance)
    pg.set_defaults(func=lambda a: parser.print_help())

    # init
    ig = sub.add_parser("init", help="Initialize STATE.md")
    ig.add_argument("--goal", default="")
    ig.add_argument("--scope", default="")
    ig.set_defaults(func=cmd_init)

    args = parser.parse_args()

    # Resolve plan directory
    if args.plan_dir:
        resolved_plan_dir = args.plan_dir
    else:
        resolved_plan_dir = PLAN_DIR

    # Inject resolved path into state functions
    import sys as _sys_mod
    _sys_mod.modules[__name__].PLAN_DIR = resolved_plan_dir

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
