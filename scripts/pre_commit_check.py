#!/usr/bin/env python3
"""
Pre-commit quality gate for blog posts.
Blocks commits when a staged blog post scores below the minimum threshold.

Install as a git hook:
  cp scripts/pre_commit_check.py .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit

Or via install.sh (recommended).

Usage:
  python3 scripts/pre_commit_check.py [--threshold N] [--warn-only]

Options:
  --threshold N   Minimum score to allow commit (default: 70)
  --warn-only     Print warning but do not block the commit
  --verbose       Show full score breakdown for each post
"""

import subprocess
import sys
import os
import json
import argparse


DEFAULT_THRESHOLD = 70
BLOG_EXTENSIONS = {".md", ".mdx", ".html"}


def get_staged_blog_files():
    """Return list of staged blog post files (added or modified)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    staged = []
    for path in result.stdout.strip().splitlines():
        ext = os.path.splitext(path)[1].lower()
        if ext not in BLOG_EXTENSIONS:
            continue
        # Skip non-blog files: docs, skills, agents, scripts, tests
        skip_prefixes = (
            "docs/", "skills/", "agents/", "scripts/", "tests/",
            ".github/", ".claude-plugin/", "personas/", "competitors/",
            "outreach/", "repurposed/", "email-sequences/",
            "translations/", "performance/", "publish/",
        )
        if any(path.startswith(p) for p in skip_prefixes):
            continue
        if os.path.exists(path):
            staged.append(path)

    return staged


def score_post(file_path):
    """Run analyze_blog.py on a single post and return its score."""
    script = os.path.join(os.path.dirname(__file__), "analyze_blog.py")
    if not os.path.exists(script):
        # Try installed location
        home = os.path.expanduser("~")
        script = os.path.join(home, ".claude", "skills", "blog", "scripts", "analyze_blog.py")

    if not os.path.exists(script):
        return None, "analyze_blog.py not found — install via install.sh"

    result = subprocess.run(
        [sys.executable, script, file_path, "--format", "json"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None, f"Analysis failed: {result.stderr.strip()}"

    try:
        data = json.loads(result.stdout)
        # Handle both single-post and batch output formats
        if isinstance(data, list):
            data = data[0]
        score = data.get("total_score") or data.get("score")
        return score, data
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return None, f"Could not parse score: {e}"


def format_breakdown(data):
    """Format score breakdown for verbose output."""
    if not isinstance(data, dict):
        return ""
    categories = data.get("categories", {})
    if not categories:
        return ""
    lines = []
    for cat, score in categories.items():
        lines.append(f"    {cat}: {score}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pre-commit blog quality gate")
    parser.add_argument(
        "--threshold", type=int, default=DEFAULT_THRESHOLD,
        help=f"Minimum score to allow commit (default: {DEFAULT_THRESHOLD})"
    )
    parser.add_argument(
        "--warn-only", action="store_true",
        help="Print warning but do not block the commit"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show full score breakdown for each post"
    )
    args = parser.parse_args()

    staged_files = get_staged_blog_files()

    if not staged_files:
        sys.exit(0)  # No blog files staged, allow commit

    print(f"\n🔍 Blog quality gate (threshold: {args.threshold}/100)")
    print(f"   Checking {len(staged_files)} staged blog file(s)...\n")

    failures = []
    warnings = []

    for file_path in staged_files:
        score, data = score_post(file_path)

        if score is None:
            # Analyzer not available — warn but don't block
            print(f"  ⚠️  {file_path}")
            print(f"      Could not score: {data}")
            warnings.append(file_path)
            continue

        status = "✅" if score >= args.threshold else "❌"
        print(f"  {status} {file_path}")
        print(f"      Score: {score}/100 (threshold: {args.threshold})")

        if args.verbose and isinstance(data, dict):
            breakdown = format_breakdown(data)
            if breakdown:
                print(breakdown)

        if score < args.threshold:
            failures.append((file_path, score))

    print()

    if failures:
        print("❌ COMMIT BLOCKED — the following posts are below the quality threshold:\n")
        for file_path, score in failures:
            gap = args.threshold - score
            print(f"   {file_path}: {score}/100 (needs +{gap} points)")
        print()
        print("To fix:")
        print("  /blog analyze <file>     — see detailed improvement recommendations")
        print("  /blog rewrite <file>     — full optimization pass")
        print("  /blog seo-check <file>   — SEO-specific fixes")
        print()
        print("To bypass (use sparingly):")
        print("  git commit --no-verify   — skip this hook")
        print("  --warn-only flag         — warn but allow commit")
        print()

        if args.warn_only:
            print("⚠️  warn-only mode: commit allowed despite quality failures\n")
            sys.exit(0)
        else:
            sys.exit(1)

    if warnings:
        print(f"⚠️  {len(warnings)} file(s) could not be scored — install.sh sets up the analyzer")

    print("✅ All staged blog posts meet the quality threshold. Proceeding.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
