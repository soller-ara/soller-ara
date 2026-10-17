#!/usr/bin/env python3
"""Confirm existing Instagram sends using GETs; never create or delete media."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

try:
    import publish_own_social as publisher
    from instagram_delivery import matching_media, read_account_media
except ModuleNotFoundError:
    from scripts import publish_own_social as publisher
    from scripts.instagram_delivery import matching_media, read_account_media

ROOT = Path(__file__).resolve().parents[1]
PENDING = {"deferred", "publishing", "verification_required"}


def pending_entries(log: dict) -> list[dict]:
    latest = {}
    successes = set()
    for entry in log["entries"]:
        if entry.get("platform") != "instagram":
            continue
        latest[entry.get("post_id")] = entry
        if entry.get("status") == "success":
            successes.add(entry.get("post_id"))
    return [entry for identifier, entry in latest.items()
            if identifier and identifier not in successes and entry.get("status") in PENDING]


def read_post_ids(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    posts = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(posts, list) or any(not isinstance(post, dict)
            or not isinstance(post.get("id"), str) or not post["id"] for post in posts):
        raise ValueError(f"No es pot comprovar l'inventari de publicacions: {path.name}")
    identifiers = {post["id"] for post in posts}
    if len(identifiers) != len(posts):
        raise ValueError(f"Identificadors duplicats: {path.name}")
    return identifiers


def reconcile(log: dict, media: list[dict], manual_ids: set[str], public_ids: set[str],
              detail_exists, now: str) -> tuple[dict, dict]:
    result = deepcopy(log)
    counts = {"confirmed": 0, "cancelled_removed": 0, "unmatched": 0, "ambiguous": 0}
    for entry in pending_entries(result):
        source = str(entry.get("source") or "Font original") if entry.get("mode") == "automatic_collected" else None
        try:
            matches = matching_media(media, str(entry.get("post_url") or ""), source)
        except ValueError:
            counts["unmatched"] += 1
            continue
        if len(matches) > 1:
            counts["ambiguous"] += 1
            continue
        identifier = entry["post_id"]
        removed = (entry.get("mode") != "automatic_collected"
                   and re.fullmatch(r"soller-ara-[a-f0-9]{16}", identifier)
                   and entry.get("post_url") == f"https://soller-ara.github.io/soller-ara/noticies/{identifier}.html"
                   and identifier not in manual_ids and identifier not in public_ids
                   and not detail_exists(identifier))
        if not matches and not removed:
            counts["unmatched"] += 1
            continue
        entry["previous_status"] = entry["status"]
        entry["previous_error"] = entry.get("error", "")
        entry["verified_at"] = now
        entry["retry_requested"] = False
        entry["error"] = ""
        # Keep recorded_at: confirming an old send is not a new publication.
        if matches:
            receipt = matches[0]
            entry.update(status="success", remote_id=str(receipt["id"]),
                         remote_url=str(receipt.get("permalink") or ""),
                         published_at=str(receipt.get("timestamp") or ""),
                         stage="verified_existing_media", verification_method="exact_article_url_and_source")
            counts["confirmed"] += 1
        else:
            entry.update(status="cancelled", stage="post_removed",
                         cancellation_reason="Manual publication removed; no matching Instagram media")
            counts["cancelled_removed"] += 1
    return result, counts


def main() -> int:
    log = publisher.load_publish_log()
    if not pending_entries(log):
        print("INSTAGRAM_RECONCILE: no pending deliveries")
        return 0
    manual_ids = read_post_ids(ROOT / "data/manual_posts.json")
    public_ids = read_post_ids(ROOT / "data/posts.json")
    _, _, ig_id, username = publisher.discover_accounts()
    if username.casefold() != "soller.ara":
        raise ValueError("El compte Instagram vinculat no és @soller.ara.")

    def read_graph(path, method="GET", **kwargs):
        if method != "GET":
            raise ValueError("La reconciliació només permet lectures de Meta.")
        return publisher.graph(path, method="GET", **kwargs)

    # A failed/incomplete read raises before any log write or cancellation.
    media = read_account_media(read_graph, ig_id, publisher.TOKEN)
    updated, counts = reconcile(log, media, manual_ids, public_ids,
                               lambda identifier: (ROOT / "noticies" / f"{identifier}.html").exists(),
                               datetime.now(timezone.utc).isoformat())
    if counts["confirmed"] or counts["cancelled_removed"]:
        temporary = publisher.LOG_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(publisher.LOG_FILE)
    print("INSTAGRAM_RECONCILE " + json.dumps({"account": username, "media_checked": len(media), **counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
