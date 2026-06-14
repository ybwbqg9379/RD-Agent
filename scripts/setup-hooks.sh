#!/usr/bin/env bash
# [FORK] One-time activation of this fork's local git hooks (see FORK.md §3).
# Git hooks are NOT shared by clone; this points git at the tracked .githooks/
# directory so the commit-msg gate applies to everyone working in this clone.
#
#   Run once after cloning:  ./scripts/setup-hooks.sh
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

echo "✓ core.hooksPath -> .githooks (commit-msg gate active)"
echo "  Verify: git config --get core.hooksPath"
