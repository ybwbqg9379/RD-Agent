# [FORK] Private package for this fork's own logic (see FORK.md §2).
#
# Anything we build that is NOT a minimal edit to an upstream file lives here, so
# it never collides with upstream on `git merge upstream/main`.
#
# Modules:
#   us_qlib_backtest  — drive qlib's `qrun` directly on US data, bypassing
#                       RD-Agent's loop wrapper (which has a China-only / docker-SDK
#                       bug on US data; see FORK.md §9.7). Engine-only, no LLM.
