#!/usr/bin/env python3
"""
Prometheus -> Metis -> Momus 规划管线
======================================
Inspired by oh-my-openagent's planning pipeline.

Three-phase structured planning:
  Phase 1: Prometheus  --- 访谈 / 需求澄清
  Phase 2: Metis       --- 差距分析（当前状态 -> 目标状态）
  Phase 3: Momus       --- 审查 & 优化

Usage:
  python planning_pipeline.py                                            # Interactive mode
  python planning_pipeline.py --goal "实现X" --goal "实现Y"               # Batch mode
  python planning_pipeline.py --goal "..." --project trendscope          # Scoped
  python planning_pipeline.py --dry-run                                  # Preview only
  python planning_pipeline.py --graph                                    # Include graph context

Output:
  .plan/task_plan.md     --- 结构化任务分解
  .plan/progress.md      --- 进度追踪 + 决策日志
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "/sessions/zen-awesome-gauss/mnt/projects")
PLAN_DIR = os.path.join(PROJECTS_ROOT, ".plan")
GRAPH_PATH = os.environ.get("GRAPH_PATH") or os.path.join(PROJECTS_ROOT, "graphify-output", "graph.json")


# --- Graph Enrichment ---------------------------------------------------------


def query_graph(goal_keywords: list[str], max_results: int = 8) -> list[dict]:
    """Query graphify knowledge graph for nodes related to goal keywords.

    Returns relevant community and node summaries.
    """
    if not os.path.isfile(GRAPH_PATH):
        return []

    try:
        with open(GRAPH_PATH, "r") as f:
            g = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    hits = []
    for n in g["nodes"]:
        label = n.get("label", "").lower()
        cn = n.get("community_name", "").lower()
        for kw in goal_keywords:
            kw = kw.lower().strip()
            if not kw or len(kw) < 2:
                continue
            if kw in label or kw in cn:
                hits.append({
                    "label": n.get("label", "?"),
                    "community": n.get("community_name", "?"),
                    "origin": n.get("_origin", "?"),
                    "file_type": n.get("file_type", "?"),
                    "source": n.get("source_file", "").split("/")[-1],
                })
                break

    seen = set()
    unique = []
    for h in hits:
        key = f"{h['label']}|{h['community']}"
        if key not in seen:
            seen.add(key)
            unique.append(h)

    by_community = defaultdict(list)
    for h in unique:
        by_community[h["community"]].append(h)

    results = []
    for cn, nodes in sorted(by_community.items(), key=lambda x: -len(x[1]))[:max_results]:
        semantic = sum(1 for n in nodes if n["origin"] == "semantic")
        results.append({
            "community": cn or "(unassigned)",
            "node_count": len(nodes),
            "semantic_count": semantic,
            "examples": [n["label"] for n in nodes[:5]],
        })

    return results


def enrich_gaps_with_graph(gaps: list[dict], context: dict):
    """Augment gap descriptions with graph knowledge."""
    goal = context.get("goal", "")
    keywords = [w for w in goal.replace("：", " ").replace("，", " ").split() if len(w) > 1]
    keywords.extend([
        "shared-models", "trendscope", "Multi-Publish", "auth", "JWT",
        "pipeline", "video", "publish", "prompt", "orchestrator",
    ])

    graph_hits = query_graph(keywords)
    if not graph_hits:
        return

    lines = ["图谱上下文:"]
    for hit in graph_hits:
        ex = ", ".join(hit["examples"][:3])
        sem = " \U0001f4d6" if hit["semantic_count"] > 0 else ""
        lines.append(f"  - {hit['community']}: {hit['node_count']} nodes {ex}{sem}")

    gaps.append({
        "area": "知识图谱上下文",
        "current": "图谱已构建 (11,712 节点, 17,171 边)",
        "desired": "查询并利用图谱信息辅助规划",
        "effort": "low",
        "action": "\n".join(lines),
    })


# --- Phase 1: Prometheus --- Interview Engine ---------------------------------


def prometheus_interview(goals: list[str] | None = None) -> dict:
    """Phase 1: Clarify requirements through structured interview."""
    context = {
        "goal": goals[0] if goals else "",
        "scope": "all" if not goals else "",
        "constraints": "4G ECS, Python 3.12, Node 22, aiosqlite WAL",
        "success": "pytest/npm test all green",
        "risks": "",
        "priority": "core first",
        "timestamp": datetime.now().isoformat(),
    }
    if goals and len(goals) > 1:
        context["goal"] = goals[0]
        context["scope"] = " + ".join(goals[1:]) if len(goals) <= 4 else "multiple items"
    return context


# --- Phase 2: Metis --- Gap Analysis ------------------------------------------


def metis_gap_analysis(context: dict) -> list[dict]:
    """Phase 2: Analyze current state vs desired state."""
    gaps = []
    goal = context.get("goal", "").lower()
    scope = context.get("scope", "all")

    projects_in_scope = []
    if scope and scope != "all":
        for p in scope.replace("，", ",").replace("、", ",").split(","):
            p = p.strip()
            if p:
                projects_in_scope.append(p)
    else:
        projects_in_scope = [
            "shared-models", "content-aggregator-shared", "platform-orchestrator",
            "content-aggregator", "smart-sentence-splitter", "prompt-engine",
            "trendscope", "Story2Video", "Multi-Publish",
        ]

    for project in projects_in_scope:
        proj_path = os.path.join(PROJECTS_ROOT, project)
        if not os.path.isdir(proj_path):
            gaps.append({
                "area": f"{project}/ --- project dir",
                "current": "not found", "desired": "exists and accessible",
                "effort": "unknown", "action": f"check if {project} is in workspace",
            })
            continue
        for fname in [".clinerules", "CLAUDE.md"]:
            if not os.path.isfile(os.path.join(proj_path, fname)):
                gaps.append({
                    "area": f"{project}/{fname}",
                    "current": "not found", "desired": f"{fname} exists",
                    "effort": "low", "action": f"create {project}/{fname}",
                })
        if not os.path.isfile(os.path.join(proj_path, "AGENTS.md")):
            gaps.append({
                "area": f"{project}/AGENTS.md",
                "current": "not found", "desired": "AGENTS.md exists",
                "effort": "low", "action": f"run init-deep for {project}/AGENTS.md",
            })

    goal_lower = goal.lower()
    if any(kw in goal_lower for kw in ["team mode", "multi-member", "multi-agent", "tmux", "p3"]):
        gaps.append({
            "area": "Team Mode Architecture",
            "current": "single-agent execution",
            "desired": "multi-agent parallel orchestration + communication + visualization",
            "effort": "high",
            "action": "design Team Mode: subagent scheduler, message bus, visual layout",
        })
    if any(kw in goal_lower for kw in ["model routing", "multi-model", "路由", "p2"]):
        gaps.append({
            "area": "Multi-Model Routing",
            "current": "single model call",
            "desired": "categorized routing (visual->Gemini, deep->DeepSeek/Claude, quick->GPT-4o-mini)",
            "effort": "medium",
            "action": "implement routing config + model selector",
        })
    if any(kw in goal_lower for kw in ["notepad", "wisdom", "accumulation", "积累", "p1"]):
        gaps.append({
            "area": "Wisdom Accumulation --- notepads",
            "current": "single MEMORY.md + scattered memory/*.md",
            "desired": "structured .plan/notepads/ (learnings/decisions/issues/verification)",
            "effort": "medium",
            "action": "implement notepads + auto-extraction hooks",
        })
    if any(kw in goal_lower for kw in ["planning", "prometheus", "规划", "p1"]):
        gaps.append({
            "area": "Prometheus Planning Pipeline",
            "current": "no structured planning flow",
            "desired": "3-phase pipeline: interview -> gap analysis -> review",
            "effort": "medium",
            "action": "implement planning_pipeline.py",
        })
    return gaps


# --- Phase 3: Momus --- Review Engine -----------------------------------------


def momus_review(context: dict, gaps: list[dict]) -> list[dict]:
    """Phase 3: Review the plan for completeness and quality."""
    findings = []
    if len(context.get("goal", "")) < 10:
        findings.append({"check": "goal_clear", "status": "WARN", "note": "goal too short, may be ambiguous"})
    if not context.get("scope"):
        findings.append({"check": "scope_defined", "status": "WARN", "note": "scope undefined, will run on all projects"})
    if not gaps:
        findings.append({"check": "gaps_actionable", "status": "INFO", "note": "no gaps found, current state close to target"})

    effort_counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    for g in gaps:
        effort_counts[g.get("effort", "unknown")] += 1
    findings.append({
        "check": "effort_estimated", "status": "OK",
        "note": f"Low: {effort_counts['low']}, Med: {effort_counts['medium']}, High: {effort_counts['high']}, Unknown: {effort_counts['unknown']}",
    })
    return findings


# --- Output generators ---------------------------------------------------------


def generate_task_plan(context: dict, gaps: list[dict], findings: list[dict]) -> str:
    lines = [
        f"# Planning Pipeline Report",
        f"# Goal: {context['goal'] or '(unspecified)'}",
        f"# Created: {context.get('timestamp', datetime.now().isoformat()[:10])}",
        f"# Scope: {context.get('scope', 'all')}",
        "",
        "## Interview Summary (Prometheus)",
        "",
    ]
    for k, v in context.items():
        if k != "timestamp":
            lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Gap Analysis (Metis)")
    lines.append("")

    if gaps:
        lines.append("| # | Area | Current | Desired | Effort | Action |")
        lines.append("|---|------|---------|---------|--------|--------|")
        for i, g in enumerate(gaps, 1):
            action_short = g["action"].replace("\n", " ")[:60]
            lines.append(f"| {i} | {g['area']} | {g['current']} | {g['desired']} | {g['effort']} | {action_short} |")
    else:
        lines.append("No gaps identified.")
    lines.append("")

    if findings:
        lines.append("## Review Findings (Momus)")
        lines.append("")
        for f in findings:
            icon = {"OK": "✅", "WARN": "⚠️", "INFO": "ℹ️"}.get(f["status"], "?")
            lines.append(f"- {icon} [{f['check']}] {f['note']}")

    lines.append("")
    lines.append("---")
    lines.append(f"_Generated by planning_pipeline.py at {datetime.now().isoformat()[:19]}_")
    return "\n".join(lines)


def generate_progress(context: dict, gaps: list[dict], findings: list[dict]) -> str:
    total = len(gaps)
    effort_by_level = defaultdict(int)
    for g in gaps:
        effort_by_level[g.get("effort", "unknown")] += 1

    lines = [
        "# Progress",
        "",
        "## Current State",
        f"- Goal: {context.get('goal', '(unspecified)')}",
        f"- Gaps found: {total}",
        f"  - High effort: {effort_by_level.get('high', 0)}",
        f"  - Medium effort: {effort_by_level.get('medium', 0)}",
        f"  - Low effort: {effort_by_level.get('low', 0)}",
        f"- Momus findings: {len(findings)}",
        f"- Generated: {context.get('timestamp', datetime.now().isoformat()[:19])}",
        "",
        "## Task List",
        "",
    ]

    if gaps:
        for i, g in enumerate(gaps, 1):
            priority = {"high": "P0", "medium": "P1", "low": "P2", "unknown": "P3"}.get(g.get("effort", "unknown"), "P3")
            lines.append(f"- [ ] **[{priority}]** {g['area']} --- {g['action'].split(chr(10))[0]}")
            lines.append(f"      Effort: {g['effort']} | Desired: {g['desired']}")
            lines.append("")
    else:
        lines.append("No tasks identified.")

    lines.append("## Decisions")
    lines.append("")
    lines.append("_No decisions recorded yet._")
    lines.append("")
    lines.append("## Blockers")
    lines.append("")
    lines.append("_No blockers identified._")

    return "\n".join(lines)


# --- CLI ----------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus -> Metis -> Momus planning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %% python planning_pipeline.py --goal "implement X" --goal "scope Y"
  %% python planning_pipeline.py --goal "refactor auth" --dry-run
  %% python planning_pipeline.py --graph --goal "add video pipeline"
        """,
    )
    parser.add_argument("--goal", "-g", action="append", help="Project goal (can be specified multiple times)")
    parser.add_argument("--project", "-p", help="Scope to a specific project")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Print plan without writing files")
    parser.add_argument("--graph", action="store_true", help="Enrich gap analysis with knowledge graph context")
    parser.add_argument("--out", "-o", default=PLAN_DIR, help="Output directory (default: .plan/)")

    args = parser.parse_args()

    # Phase 1: Prometheus
    print("> Phase 1: Prometheus --- Interview", file=sys.stderr)
    context = prometheus_interview(args.goal)
    if args.project:
        context["scope"] = args.project
    print(f"  Goal: {context['goal']}", file=sys.stderr)
    print(f"  Scope: {context['scope']}", file=sys.stderr)

    # Phase 2: Metis
    print("> Phase 2: Metis --- Gap Analysis", file=sys.stderr)
    gaps = metis_gap_analysis(context)
    print(f"  Found {len(gaps)} gaps", file=sys.stderr)

    # Graph enrichment
    if args.graph:
        print("> Graph enrichment active", file=sys.stderr)
        enrich_gaps_with_graph(gaps, context)
        print(f"  After graph enrichment: {len(gaps)} gaps", file=sys.stderr)

    # Phase 3: Momus
    print("> Phase 3: Momus --- Review", file=sys.stderr)
    findings = momus_review(context, gaps)
    print(f"  {len(findings)} findings", file=sys.stderr)

    # Generate outputs
    plan = generate_task_plan(context, gaps, findings)
    progress = generate_progress(context, gaps, findings)

    if args.dry_run:
        print("\n" + plan)
        print("\n" + progress)
        return

    # Write files
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(PROJECTS_ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)

    plan_path = os.path.join(out_dir, "task_plan.md")
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(plan)
    print(f"  -> task_plan.md written ({os.path.getsize(plan_path)} bytes)", file=sys.stderr)

    progress_path = os.path.join(out_dir, "progress.md")
    with open(progress_path, "w", encoding="utf-8") as f:
        f.write(progress)
    print(f"  -> progress.md written ({os.path.getsize(progress_path)} bytes)", file=sys.stderr)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
