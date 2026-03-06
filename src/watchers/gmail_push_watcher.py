"""Gmail Push Watcher — uses Google Cloud PubSub for real-time email notifications.

This is the cloud-deployed complement to gmail_watcher.py.
Instead of polling, Google pushes a notification to our PubSub topic
the moment a new email arrives — zero latency.

Setup (one-time):
    python scripts/setup_gmail_push.py

Requirements:
    - GMAIL_PUBSUB_PROJECT env var (Google Cloud project ID)
    - GMAIL_PUBSUB_TOPIC env var (e.g. 'projects/my-proj/topics/gmail-push')
    - GMAIL_PUBSUB_SUBSCRIPTION env var (e.g. 'projects/my-proj/subscriptions/gmail-sub')
    - google-cloud-pubsub package: pip install google-cloud-pubsub

How it works:
    1. Gmail watches your inbox and publishes a notification to PubSub
       whenever historyId changes.
    2. This watcher PULLS from the subscription (no public URL needed).
    3. We use Gmail History API to fetch the actual new messages.
    4. Falls back to polling if PubSub is not configured.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from base64 import b64decode
from pathlib import Path

from src.core.config import Config
from src.watchers.gmail_watcher import GmailWatcher

log = logging.getLogger(__name__)

_WATCH_RENEWAL_INTERVAL = 6 * 24 * 3600  # 6 days (Gmail watch expires every 7 days)


class GmailPushWatcher:
    """Listens to Gmail push notifications via Google Cloud PubSub pull subscription.

    Wraps GmailWatcher for the actual message processing — only the triggering
    mechanism changes (push vs poll).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._project = os.environ.get("GMAIL_PUBSUB_PROJECT", "")
        self._topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
        self._subscription = os.environ.get("GMAIL_PUBSUB_SUBSCRIPTION", "")
        self._watcher = GmailWatcher(config)
        self._running = False
        self._watch_renewal_thread: threading.Thread | None = None

    def _is_configured(self) -> bool:
        return bool(self._project and self._topic and self._subscription)

    def _renew_gmail_watch(self) -> None:
        """Register/renew the Gmail push watch. Must be called every ≤7 days."""
        service = self._watcher._get_service()
        if service is None:
            return
        try:
            result = service.users().watch(
                userId="me",
                body={
                    "topicName": self._topic,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "INCLUDE",
                },
            ).execute()
            log.info(
                "Gmail watch registered — historyId=%s, expires=%s",
                result.get("historyId"),
                result.get("expiration"),
            )
            # Seed the watcher's history cursor
            if result.get("historyId"):
                self._watcher._last_history_id = result["historyId"]
        except Exception:
            log.exception("Failed to register Gmail push watch")

    def _watch_renewal_loop(self) -> None:
        """Periodically renew the Gmail watch (runs in background thread)."""
        self._renew_gmail_watch()
        while self._running:
            time.sleep(_WATCH_RENEWAL_INTERVAL)
            if self._running:
                self._renew_gmail_watch()

    def _process_pubsub_notification(self, message_data: bytes) -> None:
        """Handle a PubSub message from Gmail — triggers incremental scan."""
        try:
            payload = json.loads(message_data)
            history_id = payload.get("historyId")
            email_address = payload.get("emailAddress", "")
            log.info("PubSub notification: email=%s historyId=%s", email_address, history_id)
        except Exception:
            log.debug("Could not parse PubSub payload — running incremental scan anyway")

        # Trigger incremental scan to pick up the new messages
        service = self._watcher._get_service()
        if service is None:
            return

        items = self._watcher._incremental_scan(service)
        for item in items:
            path = self._watcher.create_action_file(item)
            log.info("Created action file from push: %s", path.name)

    def run_pull_loop(self) -> None:
        """Pull messages from PubSub subscription in a tight loop."""
        try:
            from google.cloud import pubsub_v1
        except ImportError:
            log.error("google-cloud-pubsub not installed. Run: pip install google-cloud-pubsub")
            return

        subscriber = pubsub_v1.SubscriberClient()
        log.info("Gmail PubSub pull loop started on %s", self._subscription)

        while self._running:
            try:
                response = subscriber.pull(
                    request={"subscription": self._subscription, "max_messages": 10},
                    timeout=30,
                )
                ack_ids = []
                for msg in response.received_messages:
                    data = b64decode(msg.message.data)
                    self._process_pubsub_notification(data)
                    ack_ids.append(msg.ack_id)

                if ack_ids:
                    subscriber.acknowledge(
                        request={"subscription": self._subscription, "ack_ids": ack_ids}
                    )
            except Exception as exc:
                if "DeadlineExceeded" not in str(exc):
                    log.exception("PubSub pull error: %s", exc)
                time.sleep(5)

    def start(self) -> None:
        """Start push watcher. Falls back to polling if PubSub not configured."""
        if not self._is_configured():
            log.info(
                "PubSub not configured (GMAIL_PUBSUB_PROJECT/TOPIC/SUBSCRIPTION missing). "
                "Falling back to incremental polling."
            )
            self._watcher.run()
            return

        self._running = True

        # Start watch renewal in background
        self._watch_renewal_thread = threading.Thread(
            target=self._watch_renewal_loop, daemon=True, name="gmail-watch-renewer"
        )
        self._watch_renewal_thread.start()

        # Pull loop (blocking)
        try:
            self.run_pull_loop()
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    watcher = GmailPushWatcher(Config())
    watcher.start()
