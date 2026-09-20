#!/usr/bin/env python3
"""Publica a Facebook/Instagram la cua de contingut recopilat de Sóller Ara.

Principis:
- atribució clara de la font;
- enllaç al contingut original;
- cap imatge de tercers: Instagram usa targetes pròpies de Sóller Ara;
- per mitjans amb headline_date_link_only no reutilitza text de l'article;
- deduplicació persistent amb data/social_publish_log.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUEUE_FILE = ROOT / "data" / "social_auto_queue.json"
LOG_FILE = ROOT / "data" / "social_publish_log.json"
CONFIG_FILE = ROOT / "social_distribution.json"
SOURCES_FILE = ROOT / "sources.json"
MODERATION_FILE = ROOT / "data" / "moderation.json"

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0").strip() or "v26.0"


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_log(log: dict) -> None:
    entries = log.get("entries") or []
    log["entries"] = entries[-1000:]
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def already_published(log: dict, post_id: str, platform: str) -> bool:
    return any(
        entry.get("post_id") == post_id and entry.get("platform") == platform
        and entry.get("status") == "success"
        for entry in log.get("entries") or []
    )


def record(log: dict, item: dict, platform: str, status: str, remote_id: str = "", error: str = "", remote_url: str = "") -> None:
    log.setdefault("entries", []).append({
        "post_id": item.get("post_id"),
        "platform": platform,
        "status": status,
        "remote_id": remote_id,
        "remote_url": remote_url,
        "title": item.get("title"),
        "post_url": item.get("original_url"),
        "source": item.get("source"),
        "source_id": item.get("source_id"),
        "mode": "automatic_collected",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    })
    save_log(log)


def graph(path: str, method: str = "GET", params: dict | None = None, token: str | None = None) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    data = None
    if method == "GET" and params:
        url += "?" + urlencode(params)
    elif method == "POST":
        data = urlencode(params or {}).encode("utf-8")

    active_token = token or TOKEN
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {active_token}",
            "Accept": "application/json",
            "User-Agent": "SollerAra-AutoPublisher/0.50",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
            error = payload.get("error") or {}
            raise RuntimeError(
                f"{error.get('message') or f'HTTP {exc.code}'} "
                f"[code={error.get('code')}, subcode={error.get('error_subcode')}]"
            ) from exc
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {exc.code}: resposta no interpretable") from exc


def discover_accounts() -> tuple[str, str, str, str]:
    payload = graph(
        "me/accounts",
        params={"fields": "id,name,access_token,tasks,instagram_business_account{id,username}"},
    )
    candidates = []
    for page in payload.get("data") or []:
        page_id = str(page.get("id") or "")
        page_name = str(page.get("name") or "")
        page_token = str(page.get("access_token") or "")
        instagram = page.get("instagram_business_account") or {}
        if page_id and page_token:
            candidates.append((
                page_name,
                page_id,
                page_token,
                str(instagram.get("id") or ""),
                str(instagram.get("username") or ""),
                page.get("tasks") or [],
            ))

    matches = [item for item in candidates if item[0].casefold() in {"soller ara", "sóller ara"}]
    if len(matches) != 1:
        raise RuntimeError("No s'ha pogut identificar de forma única la pàgina Sóller Ara.")

    page_name, page_id, page_token, ig_id, ig_username, tasks = matches[0]
    if "CREATE_CONTENT" not in tasks:
        raise RuntimeError("La pàgina Sóller Ara no retorna la tasca CREATE_CONTENT.")
    return page_id, page_token, ig_id, ig_username


def safe_summary(item: dict) -> str:
    if item.get("content_policy") == "headline_date_link_only":
        return ""
    value = str(item.get("summary") or "").strip()
    return value[:500]


def hashtag(category: str) -> str:
    mapping = {
        "alerts": "#Avisos",
        "services": "#Serveis",
        "agenda": "#Agenda",
        "culture": "#Cultura",
        "sports": "#Esports",
        "commerce": "#Comerç",
        "news": "#Actualitat",
    }
    return mapping.get(category, "#Actualitat")


def base_text(item: dict) -> str:
    parts = [
        f"Informació original: {item.get('original_url') or ''}",
        "",
        str(item.get("title") or "").strip(),
        "",
        f"Font: {item.get('source') or 'Font original'}",
    ]
    summary = safe_summary(item)
    if summary:
        parts.extend(["", summary])
    return "\n".join(parts).strip()


def publish_facebook(item: dict, page_id: str, page_token: str) -> str:
    result = graph(
        f"{page_id}/feed",
        method="POST",
        params={
            "message": base_text(item),
            "link": str(item.get("original_url") or ""),
        },
        token=page_token,
    )
    identifier = str(result.get("post_id") or result.get("id") or "")
    if not identifier:
        raise RuntimeError("Facebook no ha retornat identificador de publicació.")
    return identifier


def wait_public_image(url: str) -> None:
    if not url:
        raise RuntimeError("Falta la targeta d'imatge per Instagram.")
    last_error = ""
    for _ in range(18):
        try:
            request = Request(url, headers={"User-Agent": "SollerAra-AutoPublisher/0.50"})
            with urlopen(request, timeout=20) as response:
                content_type = str(response.headers.get("Content-Type") or "")
                if response.status == 200 and "image" in content_type.lower():
                    return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(5)
    raise RuntimeError(f"La targeta d'Instagram encara no és pública. {last_error}".strip())


def publish_instagram(item: dict, ig_id: str, ig_username: str, page_token: str) -> str:
    if not ig_id:
        raise RuntimeError("No s'ha trobat el compte Instagram vinculat a Sóller Ara.")
    if ig_username.casefold() != "soller.ara":
        raise RuntimeError("El compte Instagram vinculat no és @soller.ara.")
    image_url = str(item.get("image_url") or "")
    wait_public_image(image_url)

    caption = (
        base_text(item)
        + "\n\n"
        + f"{hashtag(str(item.get('category') or 'news'))} #Sóller #SollerAra"
    )
    container = graph(
        f"{ig_id}/media",
        method="POST",
        params={"image_url": image_url, "caption": caption},
        token=page_token,
    )
    container_id = str(container.get("id") or "")
    if not container_id:
        raise RuntimeError("Instagram no ha retornat identificador de contenidor.")

    for _ in range(12):
        state = graph(container_id, params={"fields": "status_code,status"}, token=page_token)
        status = str(state.get("status_code") or "").upper()
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"El contenidor Instagram ha fallat: {status}")
        time.sleep(5)
    else:
        raise RuntimeError("El contenidor Instagram no ha quedat preparat.")

    result = graph(
        f"{ig_id}/media_publish",
        method="POST",
        params={"creation_id": container_id},
        token=page_token,
    )
    media_id = str(result.get("id") or "")
    if not media_id:
        raise RuntimeError("Instagram no ha retornat identificador de publicació.")
    print(f"INSTAGRAM_OK account=@{ig_username or '?'} media_id={media_id}")
    return media_id


def eligible_entries(config: dict, entries: list[dict], log: dict) -> list[dict]:
    """Revalida la cua amb la configuració vigent just abans de publicar."""
    sources = load_json(SOURCES_FILE, {"sources": []})
    active_sources = {s.get("id") for s in sources.get("sources", []) if s.get("enabled", True)}
    hidden = set(load_json(MODERATION_FILE, {}).get("hidden_post_ids", []))
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=int(config.get("max_age_hours", 6)))
    selected = []
    used_sources = set()
    for entry in entries:
        source_id = entry.get("source_id")
        post_id = entry.get("post_id")
        if not post_id or post_id in hidden or source_id not in active_sources or entry.get("source_type") == "own":
            continue
        if config.get("categories", {}).get(entry.get("category") or "news", True) is False:
            continue
        try:
            published_at = datetime.fromisoformat(str(entry.get("published_at") or "").replace("Z", "+00:00"))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if not threshold <= published_at <= now:
            continue
        rules = config.get("sources", {}).get(source_id) or {}
        platforms = [p for p in ("facebook", "instagram") if p in entry.get("platforms", [])
                     and config.get("platforms", {}).get(p) and rules.get(p)
                     and not already_published(log, post_id, p)]
        if not platforms or (config.get("one_post_per_source_per_run", True) and source_id in used_sources):
            continue
        selected.append({**entry, "platforms": platforms})
        used_sources.add(source_id)
        if len(selected) >= max(1, int(config.get("max_posts_per_run", 3))):
            break
    return selected


def main() -> int:
    config = load_json(CONFIG_FILE, {"enabled": False})
    queue = load_json(QUEUE_FILE, {"enabled": False, "entries": []})
    if not config.get("enabled") or not queue.get("enabled"):
        print("SOCIAL_AUTO: desactivat; no es publica res.")
        return 0

    log = load_json(LOG_FILE, {"version": 1, "entries": []})
    entries = eligible_entries(config, queue.get("entries") or [], log)
    if not entries:
        print("SOCIAL_AUTO: cua buida.")
        return 0
    if not TOKEN:
        print("SOCIAL_AUTO_ERROR: falta META_ACCESS_TOKEN.", file=sys.stderr)
        for item in entries:
            for platform in item["platforms"]:
                record(log, item, platform, "error", error="Falta META_ACCESS_TOKEN.")
        return 1

    try:
        page_id, page_token, ig_id, ig_username = discover_accounts()
    except Exception as exc:
        print(f"SOCIAL_AUTO_ERROR: {exc}", file=sys.stderr)
        for item in entries:
            for platform in item.get("platforms") or []:
                if not already_published(log, str(item.get("post_id") or ""), platform):
                    record(log, item, platform, "error", error=str(exc))
        return 1

    errors = 0
    for item in entries:
        post_id = str(item.get("post_id") or "")
        for platform in item.get("platforms") or []:
            if already_published(log, post_id, platform):
                print(f"{platform.upper()}_SKIP post={post_id}")
                continue
            try:
                if platform == "facebook":
                    remote_id = publish_facebook(item, page_id, page_token)
                    print(f"FACEBOOK_OK post={post_id} id={remote_id}")
                elif platform == "instagram":
                    remote_id = publish_instagram(item, ig_id, ig_username, page_token)
                else:
                    continue
                remote_url = f"https://www.facebook.com/{remote_id}" if platform == "facebook" else ""
                if platform == "instagram":
                    try:
                        remote_url = str(graph(remote_id, params={"fields": "permalink"}, token=page_token).get("permalink") or "")
                    except Exception:
                        pass  # Un error de lectura no convierte un envío confirmado en fallido.
                record(log, item, platform, "success", remote_id=remote_id, remote_url=remote_url)
            except Exception as exc:
                errors += 1
                record(log, item, platform, "error", error=str(exc))
                print(f"{platform.upper()}_ERROR post={post_id}: {exc}", file=sys.stderr)

    print(f"SOCIAL_AUTO: procés acabat amb {errors} errors registrats.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
