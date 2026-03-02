#!/usr/bin/env bash
# Live vault monitor — run in a terminal alongside demo_inject.py
# Shows folder counts updating in real time

VAULT="${VAULT_PATH:-$HOME/AI_Employee_Vault}"

while true; do
  clear
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  AI Employee — Live Vault Monitor"
  echo "  Vault: $VAULT"
  echo "  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  for folder in Needs_Action Pending_Approval Approved Rejected Done Plans Logs; do
    dir="$VAULT/$folder"
    if [ -d "$dir" ]; then
      count=$(ls "$dir"/*.md 2>/dev/null | wc -l | tr -d ' ')
      files=$(ls "$dir"/*.md 2>/dev/null | xargs -I{} basename {} 2>/dev/null | head -3 | sed 's/^/    → /')
      if [ "$count" -gt 0 ]; then
        printf "  \033[1;32m%-22s\033[0m \033[1;37m%s file(s)\033[0m\n" "$folder" "$count"
        echo "$files"
      else
        printf "  \033[2m%-22s %s file(s)\033[0m\n" "$folder" "$count"
      fi
    fi
  done

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Press Ctrl+C to stop"
  sleep 1
done
