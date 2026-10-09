#!/usr/bin/env python3
"""Prova de recopilació social per Sóller Ara (només lectura).

Comprova permisos, Business Discovery de les fonts configurades, cerca de
pàgines públiques de Facebook, el hashtag #soller i etiquetes a @soller.ara.

No publica, modifica ni elimina contingut a Meta.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0").strip() or "v26.0"


def graph(path: str, params: dict | None = None, token: str | None = None) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    if params:
        url += "?" + urlencode(params)

    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token or TOKEN}",
            "Accept": "application/json",
            "User-Agent": "SollerAra-CollectionProbe/0.30",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
            error = payload.get("error") or {}
            message = str(error.get("message") or f"HTTP {exc.code}")
            code = error.get("code")
            subcode = error.get("error_subcode")
            raise RuntimeError(f"{message} [code={code}, subcode={subcode}]") from exc
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {exc.code}: resposta no interpretable") from exc


def discover() -> tuple[str, str, str]:
    payload = graph(
        "me/accounts",
        params={
            "fields": "id,name,access_token,instagram_business_account{id,username}",
        },
    )

    candidates = []
    for page in payload.get("data") or []:
        instagram = page.get("instagram_business_account") or {}
        page_token = str(page.get("access_token") or "")
        if instagram.get("id") and page_token:
            candidates.append(
                (
                    page.get("name") or "",
                    str(instagram["id"]),
                    instagram.get("username") or "",
                    page_token,
                )
            )

    for page_name, ig_id, username, page_token in candidates:
        if page_name.casefold() in {"soller ara", "sóller ara"}:
            return ig_id, username, page_token

    if len(candidates) == 1:
        _, ig_id, username, page_token = candidates[0]
        return ig_id, username, page_token

    raise RuntimeError("No s'ha pogut identificar de forma única @soller.ara.")


def probe_hashtag(ig_id: str, page_token: str) -> None:
    try:
        result = graph(
            "ig_hashtag_search",
            params={"user_id": ig_id, "q": "soller"},
            token=page_token,
        )
        data = result.get("data") or []
        if not data:
            print("HASHTAG #soller: DISPONIBLE, però Meta no ha retornat identificador.")
            return

        hashtag_id = str(data[0].get("id") or "")
        if not hashtag_id:
            print("HASHTAG #soller: resposta sense id.")
            return

        recent = graph(
            f"{hashtag_id}/recent_media",
            params={
                "user_id": ig_id,
                "fields": "id,caption,media_type,permalink,timestamp",
                "limit": 10,
            },
            token=page_token,
        )
        items = recent.get("data") or []
        print(f"HASHTAG #soller: OK · {len(items)} publicacions recents accessibles.")
    except Exception as exc:
        print(f"HASHTAG #soller: BLOQUEJAT · {exc}")


def probe_tagged(ig_id: str, page_token: str) -> None:
    try:
        tagged = graph(
            f"{ig_id}/tags",
            params={
                "fields": "id,caption,media_type,permalink,timestamp,username",
                "limit": 10,
            },
            token=page_token,
        )
        items = tagged.get("data") or []
        print(f"ETIQUETES @soller.ara: OK · {len(items)} publicacions accessibles.")
    except Exception as exc:
        print(f"ETIQUETES @soller.ara: BLOQUEJAT · {exc}")


def probe_permissions() -> None:
    try:
        payload = graph("me/permissions")
        granted = {
            item.get("permission")
            for item in payload.get("data") or []
            if item.get("status") == "granted"
        }
        for permission in (
            "instagram_basic", "pages_read_engagement", "pages_show_list",
            "instagram_content_publish", "pages_manage_posts",
        ):
            status = "CONCEDIT" if permission in granted else "NO CONCEDIT"
            print(f"PERMÍS {permission}: {status}")
    except Exception as exc:
        print(f"PERMISOS: NO VERIFICATS · {exc}")


def probe_business_discovery(ig_id: str, page_token: str) -> None:
    config_path = Path(__file__).resolve().parents[1] / "social_sources.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for source in config.get("sources") or []:
        if str(source.get("platform") or "").casefold() != "instagram":
            continue
        username = str(source.get("account") or "").lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
            continue
        credentials = [("sistema", TOKEN)]
        if page_token != TOKEN:
            credentials.append(("pàgina", page_token))
        for label, token in credentials:
            try:
                payload = graph(
                    ig_id,
                    params={"fields": (
                        f"business_discovery.username({username})"
                        "{username,media.limit(1){id,permalink,timestamp}}"
                    )},
                    token=token,
                )
                business = payload.get("business_discovery")
                if not isinstance(business, dict):
                    print(f"BUSINESS_DISCOVERY @{username} [{label}]: SENSE DADES")
                    break
                items = (business.get("media") or {}).get("data") or []
                print(f"BUSINESS_DISCOVERY @{username} [{label}]: OK · {len(items)} publicacions accessibles.")
                break
            except Exception as exc:
                print(f"BUSINESS_DISCOVERY @{username} [{label}]: BLOQUEJAT · {exc}")
                # Només contrastam el tipus de token quan Meta denega el permís.
                if "code=10" not in str(exc):
                    break


def probe_facebook_public() -> None:
    try:
        payload = graph(
            "pages/search",
            params={"q": "Policia Tutor Sóller", "fields": "id,name", "limit": 3},
        )
        pages = payload.get("data") or []
        print(f"FACEBOOK PÀGINES PÚBLIQUES: OK · {len(pages)} resultats accessibles.")
        candidates = [
            page for page in pages
            if "soller" in str(page.get("name") or "").casefold().replace("ó", "o")
            and "tutor" in str(page.get("name") or "").casefold()
            and str(page.get("id") or "").isdigit()
        ]
        if len(candidates) != 1:
            print("FACEBOOK POSTS PÚBLICS: NO VERIFICATS · pàgina no identificada de forma única.")
            return
        posts = graph(
            f"{candidates[0]['id']}/posts",
            params={"fields": "id,created_time,permalink_url", "limit": 1},
        )
        print(f"FACEBOOK POSTS PÚBLICS: OK · {len(posts.get('data') or [])} publicacions accessibles.")
    except Exception as exc:
        print(f"FACEBOOK PÀGINES/POSTS PÚBLICS: BLOQUEJAT · {exc}")


def main() -> int:
    if not TOKEN:
        print("ERROR: falta META_ACCESS_TOKEN", file=sys.stderr)
        return 2

    try:
        ig_id, username, page_token = discover()
        print(f"OK compte propi detectat: @{username or '?'}")
        probe_permissions()
        probe_business_discovery(ig_id, page_token)
        probe_facebook_public()
        probe_hashtag(ig_id, page_token)
        probe_tagged(ig_id, page_token)
        print("RESULTAT: prova de recopilació completada. No s'ha publicat res.")
        return 0
    except Exception as exc:
        print(f"ERROR Collection Probe: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
