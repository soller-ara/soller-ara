#!/usr/bin/env python3
"""Read-only check of pending manual articles already visible on Instagram."""
import json

try:
    import publish_own_social as publisher
    from instagram_delivery import matching_media, read_account_media
except ModuleNotFoundError:
    from scripts import publish_own_social as publisher
    from scripts.instagram_delivery import matching_media, read_account_media


def main() -> int:
    log = publisher.load_publish_log()
    latest = {}
    for entry in log["entries"]:
        if entry.get("platform") == "instagram" and not entry.get("mode"):
            latest[entry.get("post_id")] = entry
    pending = [entry for entry in latest.values()
               if entry.get("status") in {"deferred", "verification_required", "publishing"}]
    if not pending:
        print("INSTAGRAM_VERIFY: no hi ha enviaments pendents de verificar.")
        return 0
    _, _, ig_id, username = publisher.discover_accounts()
    if username.casefold() != "soller.ara":
        raise ValueError("El compte Instagram vinculat no és @soller.ara.")
    media = read_account_media(publisher.graph, ig_id, publisher.TOKEN)
    print(f"INSTAGRAM_VERIFY account=@{username} media_checked={len(media)} pending={len(pending)}")
    for entry in pending:
        matches = matching_media(media, entry.get("post_url") or "")
        print("INSTAGRAM_DELIVERY " + json.dumps({
            "post_id": entry.get("post_id"), "copies": len(matches),
            "media": [{key: item.get(key) for key in ("id", "permalink", "timestamp")}
                      for item in matches],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
