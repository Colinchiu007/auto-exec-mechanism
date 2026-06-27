#!/usr/bin/env python3
"""
Nyquist — 上下文窗口校验工具

检查计划文件是否能在给定的 token 预算内完成。
基于字符数/词数估算 token 用量，参考 OpenAI 的近似公式。

用法:
  python nyquist_check.py check <plan_file>               # 检查 plan 文件
  python nyquist_check.py check <plan_file> --budget 50000  # 自定义预算
  python nyquist_check.py check <plan_file> --json          # JSON 输出
  python nyquist_check.py stats                            # 显示预算参考
"""
import argparse
import json
import os
import sys
from pathlib import Path


# ── Token estimation ──────────────────────────────────────────────

# Reference: OpenAI tiktoken approximates ~4 chars/token for English
# and ~2 chars/token for CJK. We use a weighted estimate.
# Chinese-heavy text: ~1.5-2 chars/token
# English-heavy code: ~3-4 chars/token
# Default: 2.5 chars/token (conservative for mixed CJK+code)

DEFAULT_CHARS_PER_TOKEN = 2.5
DEFAULT_BUDGET = 190_000  # tokens (leave room for system prompt + instructions)
MAX_BUDGET = 1_000_000  # Sonnet 4.6 / Opus 4.6 1M-class


def count_tokens(text: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
    """Estimate token count from text length.

    Uses a simple char-based estimate. For CJK-heavy text,
    chars_per_token should be lower (e.g. 1.8).
    """
    if not text:
        return 0
    return max(1, round(len(text) / chars_per_token))


def estimate_chars_per_token(text: str) -> float:
    """Auto-detect appropriate chars_per_token based on content mix.

    CJK characters get weight 1.0, ASCII gets weight 0.35 (relative),
    so CJK-heavy text gets a lower chars_per_token.
    """
    if not text:
        return DEFAULT_CHARS_PER_TOKEN

    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '぀' <= c <= 'ヿ' or '가' <= c <= '힯')
    total = len(text)
    if total == 0:
        return DEFAULT_CHARS_PER_TOKEN

    ratio = cjk / total
    # Ratio 0 -> ~3.5, Ratio 1 -> ~1.5
    cpt = 3.5 - (ratio * 2.0)
    return max(1.5, min(4.0, cpt))


def check_file(path: str, budget: int = DEFAULT_BUDGET, chars_per_token: float | None = None) -> dict:
    """Analyze a plan file for token budget compliance."""
    if not os.path.isfile(path):
        return {
            "ok": False,
            "error": f"file not found: {path}",
        }

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if chars_per_token is None:
        cpt = estimate_chars_per_token(text)
    else:
        cpt = chars_per_token

    tokens = count_tokens(text, cpt)
    chars = len(text)
    lines = text.count("\n") + 1

    return {
        "ok": tokens <= budget,
        "path": path,
        "chars": chars,
        "lines": lines,
        "tokens_estimated": tokens,
        "chars_per_token": cpt,
        "budget": budget,
        "usage_pct": round(tokens / budget * 100, 1),
        "remaining": max(0, budget - tokens),
        "within_budget": tokens <= budget,
    }


# ── Budget reference data ─────────────────────────────────────────

BUDGET_CARD = {
    "haiku-3.5": 200_000,
    "sonnet-4": 200_000,
    "sonnet-4.6": 200_000,
    "opus-4": 200_000,
    "opus-4.6": 200_000,
    "sonnet-4-1m": 1_000_000,
    "opus-4-1m": 1_000_000,
    "gpt-4o": 128_000,
    "gpt-4.1": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "deepseek-v3": 64_000,
    "deepseek-r1": 64_000,
}


# ── CLI ───────────────────────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> int:
    """Check a plan file against token budget."""
    path = args.file
    budget = args.budget or DEFAULT_BUDGET

    result = check_file(path, budget)
    if not result.get("ok") and "error" in result:
        print(result["error"], file=sys.stderr)
        return 1

    remaining_margin = budget - result["tokens_estimated"]

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"file:     {result['path']}")
    print(f"chars:    {result['chars']:,}")
    print(f"lines:    {result['lines']:,}")
    print(f"estimate: {result['tokens_estimated']:,} tokens ({result['chars_per_token']:.1f} chars/token)")
    print(f"budget:   {budget:,} tokens")
    print(f"usage:    {result['usage_pct']}%")
    print(f"margin:   {result['remaining']:,} tokens {'✅' if result['within_budget'] else '❌ OVER BUDGET'}")

    if not result["within_budget"]:
        # Suggest chunking
        suggested_chunks = (result["tokens_estimated"] // budget) + 1
        print(f"\n⚠️  Exceeds budget by {-remaining_margin:,} tokens")
        print(f"   Consider splitting into ~{suggested_chunks} chunks of ~{result['tokens_estimated'] // suggested_chunks:,} tokens each")

    return 0 if result["within_budget"] else 1


def cmd_stats(args: argparse.Namespace) -> int:
    """Show token budget reference."""
    print("Context window reference:")
    print(f"{'Model':<20} {'Budget':>12}")
    print("-" * 34)
    for model, budget in sorted(BUDGET_CARD.items(), key=lambda x: -x[1]):
        label = f"~{budget:,} tokens"
        if budget >= 1_000_000:
            label = f"{budget // 1_000_000}M tokens"
        elif budget >= 1_000:
            label = f"{budget // 1_000}K tokens"
        print(f"  {model:<20} {label:>12}")

    agent_share = int(DEFAULT_BUDGET / 200_000 * 100)
    print(f"\nDefault Nyquist budget: {DEFAULT_BUDGET:,} tokens ({agent_share}% of 200K)")
    print(f"Reserved for system prompt + overhead: {200_000 - DEFAULT_BUDGET:,} tokens")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Nyquist — 上下文窗口校验工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  check <file>     检查计划文件是否在 token 预算内
  stats            显示上下文窗口参考数据

示例:
  %% python nyquist_check.py check .plan/task_plan.md
  %% python nyquist_check.py check .plan/task_plan.md --budget 50000
  %% python nyquist_check.py check plan.md --json
  %% python nyquist_check.py stats
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # check
    ck = sub.add_parser("check", help="Check plan file against budget")
    ck.add_argument("file", help="Path to plan file")
    ck.add_argument("--budget", "-b", type=int, default=DEFAULT_BUDGET,
                    help=f"Token budget (default: {DEFAULT_BUDGET:,})")
    ck.add_argument("--chars-per-token", "-c", type=float, default=None,
                    help="Override chars/token (default: auto-detect)")
    ck.add_argument("--json", action="store_true", help="JSON output")
    ck.set_defaults(func=cmd_check)

    # stats
    st = sub.add_parser("stats", help="Show token budget reference")
    st.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
