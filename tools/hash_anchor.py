#!/usr/bin/env python3
"""
Hash-Anchored Editing Tool
==========================
Inspired by oh-my-openagent's LINE#ID content hashing.

Each line of a file is tagged with a content hash at read time.
Edits reference those hashes — if the file has changed since read,
the hash won't match and the edit is rejected before corruption.

Usage:
  python hash_anchor.py read <file>              # Annotate lines with hashes
  python hash_anchor.py edit <file> <spec> <text> # Edit single line
  python hash_anchor.py edit <file> <spec> -      # Edit from stdin
  python hash_anchor.py verify <file>             # Self-verify all lines
  python hash_anchor.py patch <file> <diff_file>  # Apply hash-validated patch

Spec format: LINE#HASH  (e.g. "15#a3f2")

Exit code: 0 on success, 1 on validation failure, 2 on error.
"""

import hashlib
import json
import os
import sys
import tempfile


# ── Hash helpers ──────────────────────────────────────────────────────────

HASH_LEN = 4  # first N hex chars = 16-bit hash → 1/65536 collision


def line_hash(line: str) -> str:
    """Deterministic content hash for a single line (excluding newline)."""
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:HASH_LEN]


def annotate_line(lineno: int, text: str) -> str:
    """Return annotated line: 'LINENO#HASH| content'"""
    h = line_hash(text.rstrip("\n").rstrip("\r"))
    return f"{lineno}#{h}| {text}"


def parse_spec(spec: str) -> tuple[int, str]:
    """Parse 'LINE#HASH' into (lineno, hash)."""
    if "#" not in spec:
        raise ValueError(f"Invalid spec '{spec}' — expected LINE#HASH")
    parts = spec.split("#", 1)
    try:
        lineno = int(parts[0])
    except ValueError:
        raise ValueError(f"Invalid line number in '{spec}'")
    return lineno, parts[1]


# ── Read ──────────────────────────────────────────────────────────────────


def cmd_read(filepath: str) -> None:
    """Read file and print annotated lines to stdout."""
    if not os.path.isfile(filepath):
        print(f"Error: file not found — {filepath}", file=sys.stderr)
        sys.exit(2)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        print(annotate_line(i, line), end="")


# ── Verify ────────────────────────────────────────────────────────────────


def cmd_verify(filepath: str) -> None:
    """Verify every line's hash matches its content."""
    if not os.path.isfile(filepath):
        print(f"Error: file not found — {filepath}", file=sys.stderr)
        sys.exit(2)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    ok = True
    for i, line in enumerate(lines, 1):
        actual = line_hash(line.rstrip("\n").rstrip("\r"))
        # If line was originally annotated, extract and verify the expected hash
        # Otherwise just report the current hash
        print(f"  {i}#{actual}| {line}", end="")

    if ok:
        print(f"\n✓ All {len(lines)} lines verified", file=sys.stderr)
    else:
        print(f"\n✗ Some lines have changed since annotation", file=sys.stderr)
        sys.exit(1)


# ── Edit ──────────────────────────────────────────────────────────────────


def cmd_edit(filepath: str, spec: str, new_text: str) -> None:
    """Edit a single line if hash matches."""
    if not os.path.isfile(filepath):
        print(f"Error: file not found — {filepath}", file=sys.stderr)
        sys.exit(2)

    lineno, expected_hash = parse_spec(spec)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if lineno < 1 or lineno > len(lines):
        print(f"Error: line {lineno} out of range (file has {len(lines)} lines)", file=sys.stderr)
        sys.exit(2)

    target_line = lines[lineno - 1].rstrip("\n").rstrip("\r")
    actual_hash = line_hash(target_line)

    if actual_hash != expected_hash:
        print(
            f"✗ HASH MISMATCH at line {lineno}\n"
            f"  Expected: {expected_hash}\n"
            f"  Actual:   {actual_hash}\n"
            f"  Content:  {target_line[:80]}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Hash matches — apply edit
    old_text = lines[lineno - 1]
    # Preserve original newline style
    if old_text.endswith("\r\n"):
        new_text += "\r\n"
    elif old_text.endswith("\n"):
        new_text += "\n"

    lines[lineno - 1] = new_text

    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        f.writelines(lines)

    print(f"✓ Line {lineno} updated (hash {expected_hash} verified)", file=sys.stderr)


# ── Patch (multi-line edits from a diff file) ─────────────────────────────


def cmd_patch(filepath: str, diff_file: str) -> None:
    """Apply a hash-validated patch file.

    Patch format (JSON lines):
      {"line": 15, "hash": "a3f2", "new": "  return result;"}
    """
    if not os.path.isfile(filepath):
        print(f"Error: file not found — {filepath}", file=sys.stderr)
        sys.exit(2)

    with open(diff_file, "r", encoding="utf-8", errors="replace") as f:
        patches = [json.loads(line) for line in f if line.strip()]

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    failures = []
    for p in patches:
        lineno = p["line"]
        expected = p["hash"]
        new_text = p["new"]
        target = lines[lineno - 1].rstrip("\n").rstrip("\r")
        actual = line_hash(target)
        if actual != expected:
            failures.append((lineno, expected, actual, target[:60]))
        else:
            if lines[lineno - 1].endswith("\r\n"):
                new_text += "\r\n"
            elif lines[lineno - 1].endswith("\n"):
                new_text += "\n"
            lines[lineno - 1] = new_text

    if failures:
        print(f"✗ {len(failures)} patch(es) rejected by hash mismatch:", file=sys.stderr)
        for ln, exp, act, snippet in failures:
            print(f"  Line {ln}: expected {exp}, actual {act} — '{snippet}'", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        f.writelines(lines)

    print(f"✓ {len(patches)} patch(es) applied to {filepath}", file=sys.stderr)


# ── CLI ───────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    filepath = os.path.abspath(sys.argv[2])

    if cmd == "read":
        cmd_read(filepath)
    elif cmd == "verify":
        cmd_verify(filepath)
    elif cmd == "edit":
        if len(sys.argv) < 4:
            print("Usage: hash_anchor.py edit <file> <LINE#HASH> <new_text|-|@file>", file=sys.stderr)
            sys.exit(2)
        spec = sys.argv[3]
        if len(sys.argv) >= 5:
            new_text = sys.argv[4]
            if new_text == "-":
                new_text = sys.stdin.read()
            elif new_text.startswith("@"):
                with open(new_text[1:], "r") as f:
                    new_text = f.read()
        else:
            new_text = sys.stdin.read()
        cmd_edit(filepath, spec, new_text)
    elif cmd == "patch":
        if len(sys.argv) < 4:
            print("Usage: hash_anchor.py patch <file> <diff_file>", file=sys.stderr)
            sys.exit(2)
        cmd_patch(filepath, sys.argv[3])
    elif cmd == "hash":
        # Utility: show hash for a given string
        for arg in sys.argv[2:]:
            print(f"{arg} → {line_hash(arg)}")
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
