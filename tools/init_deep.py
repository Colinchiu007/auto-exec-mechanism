#!/usr/bin/env python3
"""
/init-deep — 层级化 AGENTS.md 自动生成
========================================
Inspired by oh-my-openagent's /init-deep command.

Scans project directories, reads existing .clinerules / CLAUDE.md / PRD,
and auto-generates hierarchical AGENTS.md files at multiple directory levels.

Usage:
  python init_deep.py                        # Scan all 9 projects
  python init_deep.py --project trendscope    # Single project
  python init_deep.py --dry-run              # Preview without writing
  python init_deep.py --llm                  # Use LLM for descriptions

Output:
  <project>/
    ├── AGENTS.md             ← project-wide agent context
    ├── src/
    │   ├── AGENTS.md         ← source-level context
    │   ├── components/
    │   │   └── AGENTS.md     ← component-level context (if applicable)
    │   └── services/
    │       └── AGENTS.md     <- service-level context (if applicable)
"""

import argparse
import os
import sys

# ── Configuration ─────────────────────────────────────────────────────────

PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "/sessions/zen-awesome-gauss/mnt/projects")

PROJECTS = [
    "shared-models",
    "content-aggregator-shared",
    "platform-orchestrator",
    "content-aggregator",
    "smart-sentence-splitter",
    "prompt-engine",
    "trendscope",
    "Story2Video",
    "Multi-Publish",
]

SOURCE_DIR_NAMES = ["src", "source", "app", "lib", "server", "frontend", "backend"]
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", "egg-info", "dist",
                ".next", "venv", ".venv", ".egg-info", "build", "assets",
                "public", "tests", "test", "crawler-engine",
                "__pycache__", ".temp_staging", ".benchmarks"}


def find_package_dirs(project_path: str) -> list[str]:
    """Heuristic: find Python/Node package directories that are src-like."""
    found = []
    try:
        for entry in os.listdir(project_path):
            full = os.path.join(project_path, entry)
            if not os.path.isdir(full) or entry.startswith(".") or entry in EXCLUDE_DIRS:
                continue
            if os.path.isfile(os.path.join(full, "__init__.py")):
                found.append(entry)
                continue
            if os.path.isfile(os.path.join(full, "package.json")):
                found.append(entry)
    except OSError:
        pass
    return found


# ── Helpers ───────────────────────────────────────────────────────────────


def read_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, OSError):
        return None


def find_source_dirs(project_path: str, project: str = "") -> list[str]:
    """Find the main source directories in a project."""
    found = []
    for name in SOURCE_DIR_NAMES:
        path = os.path.join(project_path, name)
        if os.path.isdir(path):
            found.append(name)
    pkg_dirs = find_package_dirs(project_path)
    for pkg in pkg_dirs:
        if pkg not in found:
            found.append(pkg)
    conventional = {"src", "source", "app", "lib", "server"}
    if project and project in found and any(sd in found for sd in conventional):
        found.remove(project)
    non_src = {"tests", "test", "docs", "scripts", "script", "admin", "deploy", "assets", "public"}
    found = [d for d in found
             if d not in non_src
             and not (len(d) > 2 and d[0].isdigit() and d[1].isdigit() and d[2] == "-")]
    return found


def find_subdirs(parent: str) -> list[str]:
    """Find immediate subdirectories (non-recursive, filtered)."""
    result = []
    if not os.path.isdir(parent):
        return result
    try:
        for entry in os.listdir(parent):
            full = os.path.join(parent, entry)
            if not os.path.isdir(full) or entry.startswith("."):
                continue
            if entry in EXCLUDE_DIRS:
                continue
            if "egg-info" in entry:
                continue
            if len(entry) > 2 and entry[0].isdigit() and entry[1].isdigit() and entry[2] == "-":
                continue
            result.append(entry)
    except OSError:
        pass
    return sorted(result)


def extract_rules(clinerules_content: str | None) -> list[str]:
    if not clinerules_content:
        return []
    rules = []
    for line in clinerules_content.splitlines():
        line = line.strip()
        if line.startswith("- rule:"):
            rule = line.replace("- rule:", "").strip().strip('"').strip("'")
            rules.append(rule)
    return rules


def extract_agents_md_scope(existing: str | None) -> str:
    if not existing:
        return ""
    for line in existing.splitlines():
        if line.startswith("# ") or line.startswith("> "):
            stripped = line.lstrip("# >").strip()
            if stripped and len(stripped) < 100:
                return stripped
    return ""


def detect_language(project_path: str) -> str:
    counts = {}
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in {".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".go", ".rs", ".java"}:
                counts[ext] = counts.get(ext, 0) + 1
    LANG_MAP = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript/React",
        ".js": "JavaScript", ".jsx": "JavaScript/React", ".vue": "Vue 3",
        ".go": "Go", ".rs": "Rust", ".java": "Java",
    }
    if not counts:
        return "Unknown"
    return LANG_MAP.get(max(counts, key=counts.get), "Unknown")


def count_files(project_path: str) -> int:
    total = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        total += len(files)
    return total


def gen_project_agents(project: str, project_path: str,
                       clinerules_content: str | None,
                       claude_md_content: str | None,
                       prd_content: str | None) -> str:
    rules = extract_rules(clinerules_content)
    lang = detect_language(project_path)
    file_count = count_files(project_path)
    src_dirs = find_source_dirs(project_path, project)

    lines = [
        f"# {project} — 开发规范", "",
        f"> 语言: {lang}  |  文件数: ~{file_count}  |  生成: /init-deep", "",
        "## 项目概述", "",
    ]
    if claude_md_content:
        summary = ""
        for line in claude_md_content.splitlines():
            if line.startswith("# "):
                summary = line.lstrip("# ").strip()
                break
        lines.append(f"{project}: {summary}" if summary else "参见 `CLAUDE.md` 获取完整项目说明。")
    else:
        lines.append("参见 `README.md` 或同类文档获取项目说明。")
    lines.append("")

    if src_dirs:
        lines.append("## 源目录结构"); lines.append("")
        for sd in src_dirs:
            subdirs = find_subdirs(os.path.join(project_path, sd))
            lines.append(f"- `{sd}/` — 主源码目录")
            for sub in subdirs[:8]:
                lines.append(f"  - `{sub}/`")
        lines.append("")

    if rules:
        lines.append("## 硬约束（来自 .clinerules）"); lines.append("")
        for r in rules[:8]:
            lines.append(f"- {r}")
        if len(rules) > 8:
            lines.append(f"- ... 及 {len(rules) - 8} 条其他约束")
        lines.append("")

    if prd_content:
        prd_title = ""
        for line in prd_content.splitlines():
            if line.startswith("# "):
                prd_title = line.lstrip("# ").strip()
                break
        lines.append("## PRD 参考"); lines.append("")
        lines.append(f"- PRD: `docs/PRD.md` — {prd_title or '产品需求文档'}")
        lines.append("")

    lines.append("## 入口文件"); lines.append("")
    if claude_md_content:
        lines.append("- `CLAUDE.md` — 开发指南和命令")
    if clinerules_content:
        lines.append("- `.clinerules` — 项目特定硬约束")
    if prd_content:
        lines.append("- `docs/PRD.md` — 产品需求文档")
    if src_dirs:
        lines.append(f"- `{src_dirs[0]}/` — 源码入口")
    lines.append("- `AGENTS.md` — 本文件，AI 行为规范")
    lines.append("")

    pipeline_order = [
        "trendscope", "content-aggregator", "content-aggregator-shared",
        "smart-sentence-splitter", "prompt-engine", "Story2Video", "Multi-Publish",
    ]
    if project in pipeline_order:
        idx = pipeline_order.index(project)
        upstream = pipeline_order[idx - 1] if idx > 0 else None
        downstream = pipeline_order[idx + 1] if idx < len(pipeline_order) - 1 else None
        lines.append("## 管道位置"); lines.append("")
        if upstream:
            lines.append(f"- 上游: `{upstream}/` — 数据来源")
        lines.append(f"- 当前: `{project}/`")
        if downstream:
            lines.append(f"- 下游: `{downstream}/` — 数据去向")
        lines.append("")
    return "\n".join(lines)


def gen_src_agents(project: str, src_dir_name: str, src_path: str) -> str:
    subdirs = find_subdirs(src_path)
    py_files = sorted(f for f in os.listdir(src_path) if f.endswith(".py") and os.path.isfile(os.path.join(src_path, f)))
    ts_files = sorted(f for f in os.listdir(src_path) if f.endswith((".ts", ".tsx")) and os.path.isfile(os.path.join(src_path, f)))
    lines = [
        f"# {project}/{src_dir_name} — 源码上下文", "",
        f"> 源码目录 `{src_dir_name}/`. 本文件在 AI 操作该目录代码时自动加载。", "",
        "## 目录结构", "",
    ]
    ext_blocks = [(py_files, "Python 模块"), (ts_files, "TypeScript 模块")]
    for files, heading in ext_blocks:
        if files:
            lines.append(f"### {heading}"); lines.append("")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    if subdirs:
        lines.append("### 子目录"); lines.append("")
        for d in subdirs:
            entries = find_subdirs(os.path.join(src_path, d))
            detail = f" ({len(entries)} 子目录)" if entries else ""
            lines.append(f"- `{d}/`{detail}")
        lines.append("")
    lines.extend([
        "## 编辑规范", "",
        "- 修改代码前先阅读对应模块的现有实现，理解接口契约",
        "- 遵循项目 `.clinerules` 中的架构约束",
        "- 新增文件需保持一致的命名风格",
        "- 提交前运行 `pytest` 或 `npm test` 确保无回归", "",
    ])
    return "\n".join(lines)


def gen_subdir_agents(project: str, src_dir: str, subdir: str, subdir_path: str) -> str | None:
    entries = [e for e in os.listdir(subdir_path) if os.path.isfile(os.path.join(subdir_path, e)) and not e.startswith(".")]
    if len(entries) < 3:
        return None
    lines = [
        f"# {project}/{src_dir}/{subdir} — 模块上下文", "",
        f"> 模块 `{subdir}/`. 含 {len(entries)} 个文件。", "",
        "## 文件清单", "",
    ]
    for e in sorted(entries)[:15]:
        lines.append(f"- `{e}`")
    if len(entries) > 15:
        lines.append(f"- ... 及 {len(entries) - 15} 个其他文件")
    lines.append("")
    return "\n".join(lines)


def process_project(project: str, dry_run: bool) -> dict[str, str]:
    project_path = os.path.join(PROJECTS_ROOT, project)
    if not os.path.isdir(project_path):
        print(f"  [SKIP] {project}/ — directory not found")
        return {}
    clinerules = read_file(os.path.join(project_path, ".clinerules"))
    claude_md = read_file(os.path.join(project_path, "CLAUDE.md"))
    prd = read_file(os.path.join(project_path, "docs", "PRD.md"))
    outputs = {}

    # 1. Project-level AGENTS.md
    content = gen_project_agents(project, project_path, clinerules, claude_md, prd)
    out_path = os.path.join(project_path, "AGENTS.md")
    existing = read_file(out_path)
    if existing and extract_agents_md_scope(existing):
        if "[auto]" in existing[:200] or "generated" in existing[:200].lower() or len(existing) < 100:
            outputs[out_path] = content
        else:
            print(f"  [SKIP] {project}/AGENTS.md — has manual content")
    else:
        outputs[out_path] = content

    # 2. Source-level AGENTS.md
    src_dirs = find_source_dirs(project_path, project)
    for sd in src_dirs:
        src_path = os.path.join(project_path, sd)
        if not os.path.isdir(src_path):
            continue
        outputs[os.path.join(src_path, "AGENTS.md")] = gen_src_agents(project, sd, src_path)
        # 3. Subdirectory level (3+ files)
        for subdir in find_subdirs(src_path):
            sub_path = os.path.join(src_path, subdir)
            content = gen_subdir_agents(project, sd, subdir, sub_path)
            if content:
                outputs[os.path.join(sub_path, "AGENTS.md")] = content
    return outputs


def main():
    parser = argparse.ArgumentParser(description="/init-deep — hierarchical AGENTS.md generator")
    parser.add_argument("--project", "-p", help="Process a single project (default: all 9)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without writing")
    parser.add_argument("--llm", action="store_true", help="Use LLM for descriptions (future)")
    args = parser.parse_args()
    projects = [args.project] if args.project else PROJECTS
    total_written = total_skipped = 0

    for project in projects:
        print(f"\n{'='*50}\n  {project}/\n{'='*50}")
        outputs = process_project(project, dry_run=args.dry_run)
        for out_path, content in outputs.items():
            rel = os.path.relpath(out_path, PROJECTS_ROOT)
            if args.dry_run:
                print(f"  [DRY] → {rel} ({len(content)} chars)")
                total_written += 1
            else:
                existing = read_file(out_path)
                if existing and existing == content:
                    print(f"  [SAME] {rel}")
                    total_skipped += 1
                    continue
                try:
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"  [WRITE] {rel} ({len(content)} chars)")
                    total_written += 1
                except OSError as e:
                    print(f"  [ERROR] {rel}: {e}", file=sys.stderr)
                    total_skipped += 1

    print(f"\n{'='*50}\n  Done: {total_written} written, {total_skipped} skipped\n{'='*50}")

if __name__ == "__main__":
    main()
