#!/usr/bin/env bash
set -euo pipefail

# Commits tracked/untracked repo changes and pushes to current branch.
# Safe no-op if there are no changes.

COMMIT_MSG="${1:-chore: automated project update}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository" >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"

if [ -z "$(git status --porcelain)" ]; then
  echo "No changes to commit"
  exit 0
fi

git add -A
git commit -m "$COMMIT_MSG"
git push origin "$branch"

echo "Pushed to origin/$branch"
