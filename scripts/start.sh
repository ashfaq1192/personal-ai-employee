#!/usr/bin/env bash
# Launches the AI Employee in a persistent tmux session.
# All components run in named windows — survives terminal close.
#
# Usage:
#   ./scripts/start.sh            # start and attach
#   ./scripts/start.sh --detach   # start in background
#   ./scripts/start.sh --restart  # kill existing and restart
#   ./scripts/start.sh --stop     # kill existing session

set -euo pipefail

SESSION="ai-employee"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$PROJECT_DIR/.venv/bin/activate"
ARG="${1:-}"

# -- helpers --
activate_cmd="source \"$VENV\" 2>/dev/null || true; cd \"$PROJECT_DIR\""
win() {
    # win <window-name> <command>
    local cmd="$activate_cmd && $2; echo; echo '[window: $1 exited — press enter to close]'; read"
    tmux new-window -t "$SESSION" -n "$1" "bash -c '$cmd'"
}

if ! command -v tmux &>/dev/null; then
    echo "ERROR: tmux is not installed. Install with: sudo apt-get install tmux"
    exit 1
fi

# Handle --stop
if [ "$ARG" = "--stop" ]; then
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        tmux kill-session -t "$SESSION"
        echo "Session '$SESSION' stopped."
    else
        echo "No session '$SESSION' running."
    fi
    exit 0
fi

# Handle --restart
if [ "$ARG" = "--restart" ] && tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Stopping existing session '$SESSION'..."
    tmux kill-session -t "$SESSION"
    sleep 1
fi

# Already running?
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' is already running."
    if [ "$ARG" = "--detach" ]; then
        echo "Attach with:  tmux attach -t $SESSION"
    else
        tmux attach-session -t "$SESSION"
    fi
    exit 0
fi

echo "Starting AI Employee in tmux session: '$SESSION'"

# Window 1: Orchestrator (master process — starts first)
tmux new-session -d -s "$SESSION" -n "orchestrator" \
    "bash -c '$activate_cmd && python -m src.orchestrator.orchestrator; echo; echo \"[orchestrator exited]\"; read'"

# Window 2: Gmail watcher
win "gmail" "python -m src.watchers.gmail_watcher"

# Window 3: WhatsApp webhook
win "whatsapp" "python src/cli/whatsapp_webhook.py"

# Window 4: Live logs (tails all vault log files)
tmux new-window -t "$SESSION" -n "logs" \
    "bash -c '$activate_cmd && tail -F vault/Logs/*.log 2>/dev/null || (echo \"Waiting for logs...\"; sleep 5; exec bash)'"

# Window 5: Interactive shell (for manual commands)
tmux new-window -t "$SESSION" -n "shell" \
    "bash -c '$activate_cmd && exec bash'"

# Focus the orchestrator window
tmux select-window -t "$SESSION:orchestrator"

echo ""
echo "  Session : $SESSION"
echo "  Windows : orchestrator | gmail | whatsapp | logs | shell"
echo ""
echo "  Attach  : tmux attach -t $SESSION"
echo "  Switch  : Ctrl+B then n (next) / p (prev) / 0-4 (by number)"
echo "  Detach  : Ctrl+B then d"
echo "  Stop    : ./scripts/start.sh --stop"
echo ""

if [ "$ARG" != "--detach" ]; then
    tmux attach-session -t "$SESSION"
fi
