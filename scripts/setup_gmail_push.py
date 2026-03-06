#!/usr/bin/env python3
"""One-time setup script for Gmail Push Notifications via Google Cloud PubSub.

Run this once to:
1. Create a PubSub topic and subscription in your Google Cloud project
2. Grant Gmail permission to publish to the topic
3. Register the Gmail watch

Usage:
    python scripts/setup_gmail_push.py --project my-gcp-project-id

Prerequisites:
    - Google Cloud project with PubSub API enabled
    - gcloud CLI authenticated  OR GOOGLE_APPLICATION_CREDENTIALS set
    - pip install google-cloud-pubsub

After setup, add to .env:
    GMAIL_PUBSUB_PROJECT=my-gcp-project-id
    GMAIL_PUBSUB_TOPIC=projects/my-gcp-project-id/topics/gmail-push
    GMAIL_PUBSUB_SUBSCRIPTION=projects/my-gcp-project-id/subscriptions/gmail-pull-sub
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config

TOPIC_NAME = "gmail-push"
SUBSCRIPTION_NAME = "gmail-pull-sub"
GMAIL_PUBLISHER_SA = "gmail-api-push@system.gserviceaccount.com"


def setup(project_id: str, dry_run: bool = False) -> None:
    topic_path = f"projects/{project_id}/topics/{TOPIC_NAME}"
    sub_path = f"projects/{project_id}/subscriptions/{SUBSCRIPTION_NAME}"

    print(f"Setting up Gmail Push for project: {project_id}")

    try:
        from google.cloud import pubsub_v1
        from google.api_core.exceptions import AlreadyExists
    except ImportError:
        print("ERROR: google-cloud-pubsub not installed.")
        print("Run: pip install google-cloud-pubsub")
        sys.exit(1)

    # 1. Create PubSub topic
    publisher = pubsub_v1.PublisherClient()
    print(f"\n[1/4] Creating topic: {topic_path}")
    if not dry_run:
        try:
            publisher.create_topic(request={"name": topic_path})
            print("      Created.")
        except AlreadyExists:
            print("      Already exists — OK.")

    # 2. Grant Gmail permission to publish to the topic
    print(f"\n[2/4] Granting Gmail publish permission to {GMAIL_PUBLISHER_SA}")
    if not dry_run:
        try:
            policy = publisher.get_iam_policy(request={"resource": topic_path})
            binding = next(
                (b for b in policy.bindings if b.role == "roles/pubsub.publisher"), None
            )
            if binding:
                if GMAIL_PUBLISHER_SA not in binding.members:
                    binding.members.append(f"serviceAccount:{GMAIL_PUBLISHER_SA}")
            else:
                policy.bindings.add(
                    role="roles/pubsub.publisher",
                    members=[f"serviceAccount:{GMAIL_PUBLISHER_SA}"],
                )
            publisher.set_iam_policy(request={"resource": topic_path, "policy": policy})
            print("      Permission granted.")
        except Exception as exc:
            print(f"      WARNING: Could not set IAM policy: {exc}")
            print("      You may need to do this manually in the GCP console.")

    # 3. Create pull subscription
    subscriber = pubsub_v1.SubscriberClient()
    print(f"\n[3/4] Creating subscription: {sub_path}")
    if not dry_run:
        try:
            subscriber.create_subscription(
                request={"name": sub_path, "topic": topic_path, "ack_deadline_seconds": 60}
            )
            print("      Created.")
        except AlreadyExists:
            print("      Already exists — OK.")

    # 4. Register Gmail watch
    print("\n[4/4] Registering Gmail watch...")
    if not dry_run:
        config = Config()
        from src.mcp_servers.gmail_service import GmailService
        svc = GmailService(config.gmail_credentials_path)
        service = svc._get_service()
        result = service.users().watch(
            userId="me",
            body={"topicName": topic_path, "labelIds": ["INBOX"]},
        ).execute()
        print(f"      Watch registered — historyId={result.get('historyId')}, "
              f"expires={result.get('expiration')}")

    print("\nSetup complete! Add these to your .env:")
    print(f"  GMAIL_PUBSUB_PROJECT={project_id}")
    print(f"  GMAIL_PUBSUB_TOPIC={topic_path}")
    print(f"  GMAIL_PUBSUB_SUBSCRIPTION={sub_path}")
    print("\nThen use GmailPushWatcher instead of GmailWatcher in start.sh.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup Gmail Push Notifications via PubSub")
    parser.add_argument("--project", required=True, help="Google Cloud project ID")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without executing")
    args = parser.parse_args()
    setup(args.project, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
