#!/usr/bin/env bash
# Vault Git sync — auto-commit and push/pull every 2 minutes.
#
# Handles merge conflicts by preserving both versions and creating
# an alert in Needs_Action for human resolution.
#
# Install as cron: */2 * * * * /opt/ai-employee/src/cloud/sync/vault_sync.sh
#
# Usage: bash src/cloud/sync/vault_sync.sh [--vault-path /path/to/vault]

set -euo pipefail

VAULT_PATH="${1:-${VAULT_PATH:-$HOME/AI_Employee_Vault}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFLICT_RESOLVER="$SCRIPT_DIR/conflict_resolver.py"

cd "$VAULT_PATH"

# Ensure we're in a git repo
if [ ! -d .git ]; then
    echo "ERROR: $VAULT_PATH is not a Git repository. Run vault Git init first."
    exit 1
fi

echo "[sync] Starting vault sync at $(date -Iseconds)"

# Ensure .gitignore excludes secrets
if [ ! -f .gitignore ]; then
    cat > .gitignore <<'GITIGNORE'
.env
.env.*
!.env.example
credentials.json
token.json
*_credentials.json
*.key
*.pem
*.session
whatsapp-session/
GITIGNORE
    echo "[sync] Created vault .gitignore"
fi

# Stage all changes (respects .gitignore)
git add -A

# Commit if there are changes
if ! git diff --cached --quiet; then
    git commit -m "auto-sync $(date -Iseconds)" --no-gpg-sign
    echo "[sync] Committed local changes"
else
    echo "[sync] No local changes to commit"
fi

# Pull with rebase
if git pull --rebase 2>&1; then
    echo "[sync] Pull successful"
else
    echo "[sync] Merge conflict detected — resolving..."

    # Abort rebase to get back to a clean state
    git rebase --abort 2>/dev/null || true

    # Try merge instead
    if ! git pull --no-rebase 2>/dev/null; then
        # Extract conflicted files
        CONFLICTS=$(git diff --name-only --diff-filter=U)
        if [ -n "$CONFLICTS" ]; then
            echo "[sync] Conflicted files: $CONFLICTS"

            # Run Python conflict resolver if available
            if [ -f "$CONFLICT_RESOLVER" ]; then
                python3 "$CONFLICT_RESOLVER" --vault-path "$VAULT_PATH"
            fi

            # Accept both versions and commit
            git add -A
            git commit -m "auto-sync: resolved conflicts $(date -Iseconds)" --no-gpg-sign
        fi
    fi
fi

# Push
if git push 2>&1; then
    echo "[sync] Push successful"
else
    echo "[sync] Push failed — will retry next cycle"
fi

echo "[sync] Sync complete at $(date -Iseconds)"
