#!/usr/bin/env python3
"""
Team Mode — 多 Agent 并行协作框架
====================================
Inspired by oh-my-openagent's Team Mode (Captain + multi-member architecture).

Coordinates multiple specialized agents working in parallel on decomposed tasks.

Team Roles:
  Captain     — 分解任务、分配、汇总结果、质量把控
  Researcher  — 调研、分析、信息搜集、差距识别
  Engineer    — 编码实现、测试、重构、代码审查
  Reviewer    — 审查代码和文档、质量门禁、回归验证

Usage:
  python team_mode.py init <goal>                           # Initialize a team session
  python team_mode.py assign <task> <role>                  # Assign a task to a member
  python team_mode.py status                                # Show team status
  python team_mode.py report                                # Generate team summary report
  python team_mode.py dashboard                             # Show ASCII dashboard
  python team_mode.py cleanup                               # Clean up team session
"""

import argparse
import json
import os
import sys
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "/sessions/zen-awesome-gauss/mnt/projects")
TEAM_DIR = os.path.join(PROJECTS_ROOT, ".plan", "team")

TEAM_ROLES = {
    "captain": {
        "title": "Captain",
        "icon": "⚑",
        "model": "claude-sonnet-4",
        "responsibility": "任务分解、分配、汇总、质量把控",
        "color": "blue",
    },
    "researcher": {
        "title": "Researcher",
        "icon": "⚐",
        "model": "claude-sonnet-4",
        "responsibility": "调研、分析、信息搜集、文档撰写",
        "color": "green",
    },
    "engineer": {
        "title": "Engineer",
        "icon": "⚒",
        "model": "deepseek-r1",
        "responsibility": "编码实现、测试、重构、代码审查",
        "color": "yellow",
    },
    "reviewer": {
        "title": "Reviewer",
        "icon": "✓",
        "model": "claude-opus-4",
        "responsibility": "审查、质量门禁、回归验证、安全审计",
        "color": "magenta",
    },
}

STATUS_ICONS = {
    "pending": "○",
    "in_progress": "▶",
    "completed": "✓",
    "blocked": "✗",
    "failed": "✗",
}


# ── Session Management ─────────────────────────────────────────────────


def session_path() -> str:
    return os.path.join(TEAM_DIR, "session.json")


def ensure_team_dir():
    os.makedirs(TEAM_DIR, exist_ok=True)


def load_session() -> dict:
    sp = session_path()
    if os.path.isfile(sp):
        with open(sp, "r") as f:
            return json.load(f)
    return {}


def save_session(session: dict):
    ensure_team_dir()
    with open(session_path(), "w") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def cmd_init(goal: str):
    """Initialize a new team session."""
    ensure_team_dir()
    session = load_session()
    if session and session.get("status") == "active":
        print(f"  Warning: active session already exists. Use --force to override.", file=sys.stderr)
        return

    session = {
        "goal": goal,
        "status": "active",
        "created": datetime.now().isoformat(),
        "members": {},
        "tasks": [],
        "decisions": [],
        "logs": [],
    }

    for role_id, role_info in TEAM_ROLES.items():
        session["members"][role_id] = {
            "role": role_id,
            "name": role_info["title"],
            "model": role_info["model"],
            "status": "idle",
            "current_task": None,
            "completed_tasks": 0,
            "artifacts": [],
        }

    save_session(session)
    print(f"  ✓ Team session initialized", file=sys.stderr)
    print(f"  ✓ Goal: {goal}", file=sys.stderr)
    print(f"  ✓ Members: {', '.join(m['name'] for m in session['members'].values())}", file=sys.stderr)


def cmd_assign(task_desc: str, role: str, priority: str = "medium"):
    """Assign a task to a team member."""
    session = load_session()
    if not session:
        print(f"  Error: no active session. Run 'team_mode.py init' first.", file=sys.stderr)
        sys.exit(2)

    if role not in session["members"]:
        print(f"  Error: unknown role '{role}'. Valid: {', '.join(TEAM_ROLES.keys())}", file=sys.stderr)
        sys.exit(2)

    task = {
        "id": len(session["tasks"]) + 1,
        "description": task_desc,
        "role": role,
        "status": "pending",
        "priority": priority,
        "assigned_at": datetime.now().isoformat(),
        "completed_at": None,
        "output": None,
    }

    session["tasks"].append(task)
    session["members"][role]["current_task"] = task["id"]
    session["logs"].append(f"[{datetime.now().isoformat()[:19]}] Assigned task #{task['id']} ({task_desc[:50]}...) to {role}")

    save_session(session)
    print(f"  ✓ Task #{task['id']} assigned to {role}: {task_desc}", file=sys.stderr)


def cmd_status():
    """Show team status."""
    session = load_session()
    if not session:
        print(f"  No active team session.", file=sys.stderr)
        return

    print(f"\n{'=' * 50}", file=sys.stderr)
    print(f"  Team Status — {session['goal'][:60]}...", file=sys.stderr)
    print(f"{'=' * 50}", file=sys.stderr)

    print(f"\n  Members:", file=sys.stderr)
    for role_id, member in session["members"].items():
        info = TEAM_ROLES[role_id]
        icon = STATUS_ICONS.get(member["status"], "?")
        task_ref = f" (#{member['current_task']})" if member["current_task"] else ""
        print(f"    {icon} {info['icon']} {info['title']:<12} {member['status']:<12} {info['model']:<20} {member['completed_tasks']} done{task_ref}", file=sys.stderr)

    total = len(session["tasks"])
    done = sum(1 for t in session["tasks"] if t["status"] == "completed")
    blocked = sum(1 for t in session["tasks"] if t["status"] == "blocked")
    print(f"\n  Tasks: {done}/{total} done", file=sys.stderr)
    if blocked:
        print(f"  Blocked: {blocked}", file=sys.stderr)

    if session["tasks"]:
        print(f"\n  Recent Tasks:", file=sys.stderr)
        for t in session["tasks"][-5:]:
            icon = STATUS_ICONS.get(t["status"], "?")
            print(f"    {icon} #{t['id']} [{t['role']:<12}] {t['description'][:60]}", file=sys.stderr)

    if session["decisions"]:
        print(f"\n  Decisions ({len(session['decisions'])}):", file=sys.stderr)
        for d in session["decisions"][-3:]:
            print(f"    • {d[:80]}", file=sys.stderr)

    print(file=sys.stderr)


def cmd_report():
    """Generate a comprehensive team report."""
    session = load_session()
    if not session:
        print(json.dumps({"error": "no_session"}, ensure_ascii=False))
        return

    total = len(session["tasks"])
    done = sum(1 for t in session["tasks"] if t["status"] == "completed")
    blocked = sum(1 for t in session["tasks"] if t["status"] == "blocked")
    by_role = {}
    for t in session["tasks"]:
        by_role.setdefault(t["role"], {"total": 0, "done": 0})
        by_role[t["role"]]["total"] += 1
        if t["status"] == "completed":
            by_role[t["role"]]["done"] += 1

    report = {
        "goal": session["goal"],
        "status": session["status"],
        "created": session["created"],
        "summary": {
            "total_tasks": total,
            "completed": done,
            "blocked": blocked,
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
        },
        "by_role": by_role,
        "members": {k: {"name": v["name"], "status": v["status"], "completed_tasks": v["completed_tasks"]} for k, v in session["members"].items()},
        "decisions": session["decisions"],
    }

    print(json.dumps(report, ensure_ascii=False))


def cmd_dashboard():
    """Render an ASCII dashboard for the current team session."""
    session = load_session()
    if not session:
        print("No active team session.", file=sys.stderr)
        return

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  TEAM DASHBOARD", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  Goal: {session['goal']}", file=sys.stderr)

    total = len(session["tasks"])
    done = sum(1 for t in session["tasks"] if t["status"] == "completed")
    blocked_tasks = [t for t in session["tasks"] if t["status"] == "blocked"]
    pct = round(done / total * 100, 1) if total > 0 else 0

    # Progress bar
    bar_len = 40
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  Progress: [{bar}] {pct}%", file=sys.stderr)

    print(f"\n  {'Member':<14} {'Status':<12} {'Model':<20} {'Tasks':<8} {'Current':<30}", file=sys.stderr)
    print(f"  {'-'*14} {'-'*12} {'-'*20} {'-'*8} {'-'*30}", file=sys.stderr)
    for role_id, member in session["members"].items():
        info = TEAM_ROLES[role_id]
        icon = STATUS_ICONS.get(member["status"], "?")
        member_tasks = [t for t in session["tasks"] if t["role"] == role_id]
        tasks_str = f"{sum(1 for t in member_tasks if t['status']=='completed')}/{len(member_tasks)}"
        current = ""
        if member["current_task"]:
            ct = next((t for t in session["tasks"] if t["id"] == member["current_task"]), None)
            if ct:
                current = ct["description"][:28]
        print(f"  {info['icon']} {info['title']:<10} {icon} {member['status']:<9} {member['model']:<20} {tasks_str:<8} {current}", file=sys.stderr)

    if blocked_tasks:
        print(f"\n  ⚠ BLOCKED TASKS:", file=sys.stderr)
        for t in blocked_tasks:
            print(f"    #{t['id']} [{t['role']}] {t['description'][:70]}", file=sys.stderr)

    print(f"{'='*60}", file=sys.stderr)


def cmd_cleanup():
    """Archive and clean up the team session."""
    session = load_session()
    if not session:
        print(f"  No active session.", file=sys.stderr)
        return

    # Save archive before cleanup
    ensure_team_dir()
    archive_path = os.path.join(TEAM_DIR, f"archive_{datetime.now().isoformat()[:10]}.json")
    with open(archive_path, "w") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)

    # Clear session
    session["status"] = "archived"
    save_session(session)

    print(f"  ✓ Session archived to {archive_path}", file=sys.stderr)
    print(f"  ✓ Team session cleaned up", file=sys.stderr)


def cmd_list():
    """List all archived team sessions."""
    ensure_team_dir()
    archives = sorted([f for f in os.listdir(TEAM_DIR) if f.startswith("archive_")])
    if not archives:
        print(f"  No archived sessions.", file=sys.stderr)
        return
    print(f"\n  Archived Sessions:", file=sys.stderr)
    for a in archives[-10:]:
        path = os.path.join(TEAM_DIR, a)
        with open(path) as f:
            data = json.load(f)
        goal = data.get("goal", "N/A")[:60]
        total = len(data.get("tasks", []))
        done = sum(1 for t in data.get("tasks", []) if t["status"] == "completed")
        print(f"  {a} — {goal} — {done}/{total} tasks", file=sys.stderr)
    print(file=sys.stderr)


# ── CLI ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Team Mode — 多 Agent 并行协作框架")
    sub = parser.add_subparsers(dest="command")

    init_p = sub.add_parser("init", help="Initialize a team session")
    init_p.add_argument("goal", help="Team mission goal")
    init_p.add_argument("--force", action="store_true", help="Override existing session")

    assign_p = sub.add_parser("assign", help="Assign a task to a team member")
    assign_p.add_argument("task", help="Task description")
    assign_p.add_argument("role", choices=list(TEAM_ROLES.keys()), help="Team member role")
    assign_p.add_argument("--priority", choices=["low", "medium", "high"], default="medium")

    sub.add_parser("status", help="Show team status")
    sub.add_parser("report", help="Generate team report (JSON)")
    sub.add_parser("dashboard", help="Show ASCII dashboard")
    sub.add_parser("cleanup", help="Archive and clean up session")
    sub.add_parser("list", help="List archived sessions")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args.goal)
    elif args.command == "assign":
        cmd_assign(args.task, args.role, args.priority)
    elif args.command == "status":
        cmd_status()
    elif args.command == "report":
        cmd_report()
    elif args.command == "dashboard":
        cmd_dashboard()
    elif args.command == "cleanup":
        cmd_cleanup()
    elif args.command == "list":
        cmd_list()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()