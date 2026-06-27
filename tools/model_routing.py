#!/usr/bin/env python3
"""
多模型路由配置体系
===================
Inspired by oh-my-openagent's category-based model routing.

Classifies tasks into categories and routes to the optimal model.
Supports config file override and context-aware routing.

Categories:
  visual-engineering  → Gemini 2.5 Pro   — 多模态/视觉/工程
  ultrabrain          → GPT-5             — 深度推理/复杂分析
  deep                → DeepSeek R1 / Sonnet — 代码/技术/架构
  quick               → GPT-4o-mini / Haiku  — 快速/低成本/简单
  creative            → Opus / Sonnet     — 创作/设计/文案

Usage:
  python model_routing.py classify "编写一个 FastAPI 路由"          # Classify and route
  python model_routing.py classify "生成一张产品渲染图"              # → visual-engineering
  python model_routing.py classify "这个算法的时间复杂度是多少"       # → ultrabrain
  python model_routing.py list                                      # Show routing table
  python model_routing.py route <task_id> <description>             # Route with task ID
  python model_routing.py config --show                             # Show current config
  python model_routing.py config --set visual=gemini-2.0-flash      # Override a route
"""

import argparse
import json
import os
import re
import sys

# ── Default Routing Table ──────────────────────────────────────────────

DEFAULT_ROUTES = {
    "visual-engineering": {
        "model": "gemini-2.5-pro",
        "fallback": "gemini-2.0-flash",
        "description": "多模态/视觉/工程: 图像生成、UI 设计、视频处理、前端开发",
        "keywords": [
            "image", "video", "ui", "ux", "visual", "render", "frontend",
            "design", "css", "html", "canvas", "svg", "photo", "picture",
            "multi-modal", "vision", "screenshot", "layout",
            "图像", "视频", "界面", "设计", "渲染", "前端",
        ],
        "cost": "medium",
    },
    "ultrabrain": {
        "model": "gpt-5",
        "fallback": "claude-opus-4",
        "description": "深度推理/复杂分析: 算法设计、架构决策、数学推理、数据科学",
        "keywords": [
            "algorithm", "complexity", "proof", "theorem", "analysis",
            "architecture decision", "trade-off", "optimization",
            "research", "deep reasoning", "数学", "算法", "复杂度",
            "架构决策", "推理", "分析",
        ],
        "cost": "high",
    },
    "deep": {
        "model": "deepseek-r1",
        "fallback": "claude-sonnet-4",
        "description": "代码/技术/架构: 编码实现、重构、测试、代码审查、架构设计",
        "keywords": [
            "implement", "refactor", "test", "code review", "debug",
            "function", "class", "api", "endpoint", "database",
            "migration", "schema", "pytest", "type hint",
            "实现", "重构", "测试", "代码审查", "调试",
            "函数", "类", "接口", "数据库", "架构",
        ],
        "cost": "medium",
    },
    "quick": {
        "model": "gpt-4o-mini",
        "fallback": "claude-haiku-3.5",
        "description": "快速/低成本: 简单查询、格式化、翻译、摘要、分类",
        "keywords": [
            "translate", "summarize", "format", "classify",
            "simple", "quick", "cheap", "fast", "regex",
            "parse", "convert", "template",
            "翻译", "摘要", "格式化", "分类",
            "简单", "快速",
        ],
        "cost": "low",
    },
    "creative": {
        "model": "claude-opus-4",
        "fallback": "claude-sonnet-4",
        "description": "创作/设计/文案: 写作、文案、创意设计、故事创作",
        "keywords": [
            "write", "draft", "creative", "story", "copy",
            "blog", "article", "poem", "script", "dialogue",
            "brand", "tone", "voice", "narrative",
            "写作", "创作", "文案", "故事", "博客",
            "文章", "脚本", "创意",
        ],
        "cost": "medium",
    },
}

CATEGORY_RANK = ["quick", "deep", "visual-engineering", "creative", "ultrabrain"]


# ── Config Management ──────────────────────────────────────────────────

def config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_routes.json")


def load_config() -> dict:
    """Load config with overrides from model_routes.json."""
    routes = {k: dict(v) for k, v in DEFAULT_ROUTES.items()}
    cfg = config_path()
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r") as f:
                overrides = json.load(f)
            for cat, updates in overrides.items():
                if cat in routes:
                    routes[cat].update(updates)
        except (json.JSONDecodeError, OSError):
            pass
    return routes


def save_override(key: str, value: str):
    cfg = config_path()
    overrides = {}
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r") as f:
                overrides = json.load(f)
        except json.JSONDecodeError:
            pass

    # Parse "category=model" or "category.field=value"
    if "=" in key:
        cat, field = key.split("=", 1)
    else:
        cat, field = key, "model"

    if cat not in DEFAULT_ROUTES:
        print(f"Error: unknown category '{cat}'. Valid: {', '.join(DEFAULT_ROUTES.keys())}", file=sys.stderr)
        sys.exit(2)

    if cat not in overrides:
        overrides[cat] = {}
    overrides[cat][field] = value

    with open(cfg, "w") as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)
    print(f"  ✓ {cat}.{field} = {value}", file=sys.stderr)


# ── Classifier ─────────────────────────────────────────────────────────


def classify(description: str, routes: dict | None = None) -> str:
    """Classify a task description into a routing category.

    Returns the category name based on keyword matching.
    Uses a scoring system: each keyword match adds score; highest wins.
    """
    if routes is None:
        routes = load_config()

    desc_lower = description.lower()
    scores = {cat: 0 for cat in routes}

    for cat, config in routes.items():
        for kw in config.get("keywords", []):
            if kw.lower() in desc_lower:
                scores[cat] += 1

    # Also check special patterns
    if re.search(r'\b\d+\s*[+\-*/]\s*\d+', description):
        scores["quick"] += 1  # Simple math → quick
    if re.search(r'(复杂度|complexity|o\(|big o)', desc_lower):
        scores["ultrabrain"] += 2
    if re.search(r'(pytest|unittest|test case|测试用例)', desc_lower):
        scores["deep"] += 1
    if re.search(r'(docker|k8s|deploy|deployment|ci/cd)', desc_lower):
        scores["deep"] += 1

    # Tie-breaker: prefer higher rank
    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return "quick"  # Default for unrecognized tasks

    candidates = [cat for cat, score in scores.items() if score == max_score]
    if len(candidates) == 1:
        return candidates[0]
    # Tie-break by rank (lower index = higher priority)
    candidates.sort(key=lambda c: CATEGORY_RANK.index(c) if c in CATEGORY_RANK else 99)
    return candidates[0]


# ── CLI ─────────────────────────────────────────────────────────────────


def cmd_list(routes: dict):
    print(f"\n{'Category':<22} {'Model':<22} {'Cost':<10} {'Fallback':<22}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    for cat in CATEGORY_RANK:
        if cat in routes:
            c = routes[cat]
            has_override = cat in load_config() and c.get("model") != DEFAULT_ROUTES[cat]["model"]
            marker = " *" if has_override else "  "
            print(f"  {cat:<20}{c['model']:<22}{c['cost']:<10}{c.get('fallback', '-'):<22}{marker}", file=sys.stderr)
    print(file=sys.stderr)


def cmd_classify(description: str, routes: dict):
    if not description:
        print("  Reading from stdin...", file=sys.stderr)
        description = sys.stdin.read().strip()
    if not description:
        print("Error: empty description", file=sys.stderr)
        sys.exit(2)

    category = classify(description, routes)
    config = routes[category]

    result = {
        "category": category,
        "model": config["model"],
        "fallback": config.get("fallback"),
        "cost": config["cost"],
        "description": config["description"],
    }

    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="多模型路由配置体系")
    sub = parser.add_subparsers(dest="command")

    # classify
    cls_p = sub.add_parser("classify", help="Classify a task and recommend model")
    cls_p.add_argument("description", nargs="*", help="Task description (or stdin)")

    # list
    sub.add_parser("list", help="Show routing table")

    # route (like classify but with task_id)
    route_p = sub.add_parser("route", help="Route a task (with task ID)")
    route_p.add_argument("task_id", help="Task identifier")
    route_p.add_argument("description", help="Task description")

    # config
    cfg_p = sub.add_parser("config", help="View or modify routing config")
    cfg_p.add_argument("--show", action="store_true", help="Show current config")
    cfg_p.add_argument("--set", help="Set override (e.g. visual=gemini-2.0-flash)")
    cfg_p.add_argument("--reset", help="Reset category to default")

    args = parser.parse_args()
    routes = load_config()

    if args.command == "classify":
        desc = " ".join(args.description) if args.description else ""
        cmd_classify(desc, routes)

    elif args.command == "list":
        cmd_list(routes)

    elif args.command == "route":
        result = classify(args.description, routes)
        config = routes[result]
        output = {
            "task_id": args.task_id,
            "category": result,
            "model": config["model"],
            "fallback": config.get("fallback"),
            "cost": config["cost"],
        }
        print(json.dumps(output, ensure_ascii=False))

    elif args.command == "config":
        cfg_path = config_path()
        if args.show:
            if os.path.isfile(cfg_path):
                with open(cfg_path) as f:
                    print(f.read())
            else:
                print("  (default config, no overrides)", file=sys.stderr)
        elif args.set:
            save_override(*args.set.split("=", 1))
            cmd_list(load_config())
        elif args.reset:
            if os.path.isfile(cfg_path):
                overrides = {}
                with open(cfg_path) as f:
                    overrides = json.load(f)
                overrides.pop(args.reset, None)
                with open(cfg_path, "w") as f:
                    json.dump(overrides, f, indent=2)
                print(f"  ✓ Reset {args.reset} to default", file=sys.stderr)
        else:
            cfg_p.print_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()