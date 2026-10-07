#!/usr/bin/env python3
"""Read-only check of pending manual and collected Instagram deliveries."""
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
    published = set()
    for entry in log["entries"]:
        if entry.get("platform") == "instagram":
            latest[entry.get("post_id")] = entry
            if entry.get("status") == "success":
                published.add(entry.get("post_id"))
    pending = [entry for entry in latest.values()
               if entry.get("status") in {"deferred", "verification_required", "publishing"}
               and entry.get("post_id") not in published]
    if not pending:
        print("INSTAGRAM_VERIFY: no hi ha enviaments pendents de verificar.")
        return 0
    _, _, ig_id, username = publisher.discover_accounts()
    if username.casefold() != "soller.ara":
        raise ValueError("El compte Instagram vinculat no és @soller.ara.")
    media = read_account_media(publisher.graph, ig_id, publisher.TOKEN)
    print(f"INSTAGRAM_VERIFY account=@{username} media_checked={len(media)} pending={len(pending)}")
    for entry in pending:
        source_name = str(entry.get("source") or "Font original") if entry.get("mode") == "automatic_collected" else None
        matches = matching_media(media, entry.get("post_url") or "", source_name)
        container = {}
        if entry.get("container_id"):
            try:
                state = publisher.graph(str(entry["container_id"]),
                                        params={"fields": "status_code,status"}, token=publisher.TOKEN)
                container["status"] = state.get("status_code")
            except Exception as exc:
                container["error"] = str(exc)
        print("INSTAGRAM_DELIVERY " + json.dumps({
            "post_id": entry.get("post_id"), "copies": len(matches),
            "container": container,
            "media": [{key: item.get(key) for key in ("id", "permalink", "timestamp")}
                      for item in matches],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
