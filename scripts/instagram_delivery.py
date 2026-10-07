"""Read Instagram delivery receipts before retrying a publication."""
from __future__ import annotations

import re


def read_account_media(graph, ig_id: str, token: str, max_pages: int = 20) -> list[dict]:
    """Use only GETs. An incomplete/unreadable list is never proof of absence."""
    if not ig_id:
        raise ValueError("Falta el compte Instagram per verificar les publicacions.")
    media = []
    after = None
    cursors = set()
    for _ in range(max_pages):
        params = {"fields": "id,caption,permalink,timestamp", "limit": 100}
        if after:
            params["after"] = after
        payload = graph(f"{ig_id}/media", params=params, token=token)
        data = payload.get("data")
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError("Instagram no ha retornat una llista de publicacions vàlida.")
        media.extend(data)
        paging = payload.get("paging") or {}
        if not isinstance(paging, dict):
            raise ValueError("Instagram no ha retornat una paginació vàlida.")
        if not paging.get("next"):
            return media
        after = (paging.get("cursors") or {}).get("after")
        if not after or after in cursors or not data:
            raise ValueError("No es pot completar la verificació de les publicacions Instagram.")
        cursors.add(after)
    raise ValueError("La verificació Instagram ha quedat incompleta; no es reenvia res.")


def matching_media(media: list[dict], post_url: str) -> list[dict]:
    """Match the exact stable article link, never a shared title or URL prefix."""
    if not post_url or not post_url.startswith("https://"):
        raise ValueError("Falta l'enllaç únic de la notícia per verificar Instagram.")
    pattern = re.compile(r"(?<!\S)" + re.escape(post_url) + r"(?=$|\s)")
    return [item for item in media if item.get("id")
            and pattern.search(str(item.get("caption") or ""))]
