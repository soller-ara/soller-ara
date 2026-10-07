#!/usr/bin/env python3
"""Retry explicitly requested manual Instagram sends deferred by Meta.

Uses the existing source-refresh cycle. Historical failures without a retry
request are not backfilled. Hidden/deleted posts and confirmed sends are skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    import publish_own_social as publisher
    from publication_state import instagram_is_paused
except ModuleNotFoundError:
    from scripts import publish_own_social as publisher
    from scripts.publication_state import instagram_is_paused

ROOT = Path(__file__).resolve().parents[1]
MANUAL_FILE = ROOT / "data/manual_posts.json"
MODERATION_FILE = ROOT / "data/moderation.json"
MAX_RETRIES_PER_RUN = 3


def read_list(path: Path, key: str) -> list:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"Format no vàlid: {path.name}/{key}")
    if key == "posts" and any(not isinstance(post, dict) for post in payload[key]):
        raise ValueError("Format de publicacions no vàlid.")
    return payload[key]


def pending_posts(log: dict, posts: list[dict], hidden: set[str]) -> list[dict]:
    latest = {}
    published = set()
    uncertain = set()
    for entry in log.get("entries", []):
        if entry.get("platform") != "instagram":
            continue
        identifier = entry.get("post_id")
        latest[identifier] = entry
        if entry.get("status") == "success":
            published.add(identifier)
        if entry.get("status") in {"publishing", "verification_required"}:
            uncertain.add(identifier)
    pending = {identifier: entry for identifier, entry in latest.items()
               if (entry.get("status") == "deferred" and entry.get("retry_requested") is True
                   or identifier in uncertain)
               and identifier not in published and identifier not in hidden}
    return sorted([post for post in posts if post.get("id") in pending
                   and post.get("source_type") == "own"],
                  key=lambda post: pending[post["id"]].get("recorded_at") or "")


def main() -> int:
    log = publisher.load_publish_log()
    if instagram_is_paused(log):
        print("MANUAL_RETRY: Instagram en pausa; es conserven els pendents.")
        return 0
    posts = read_list(MANUAL_FILE, "posts")
    hidden = set(read_list(MODERATION_FILE, "hidden_post_ids"))
    selected = pending_posts(log, posts, hidden)[:MAX_RETRIES_PER_RUN]
    errors = 0
    for post in selected:
        publisher.POST_ID = post["id"]
        publisher.POST_URL = post.get("url") or ""
        publisher.TITLE = post.get("title") or ""
        publisher.BODY = post.get("summary") or ""
        publisher.ORIGINAL_URL = post.get("original_url") or ""
        publisher.SOURCE_NAME = post.get("source") or ""
        publisher.IMAGE_URL = post.get("media_url") or ""
        publisher.CONFIRMATION = "PUBLICAR"
        publisher.DO_FACEBOOK = False
        publisher.DO_INSTAGRAM = True
        result = publisher.main()
        errors += bool(result)
        print(f"MANUAL_RETRY post={post['id']} result={result}")
        if instagram_is_paused(publisher.load_publish_log()):
            break
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
