#!/usr/bin/env python3
"""Publica una entrada pròpia de Sóller Ara a les xarxes pròpies de Meta.

No modifica el feed: la publicació principal s'ha creat abans amb add_own_post.py.
Facebook admet publicació de text; Instagram necessita una imatge pública.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from instagram_delivery import (InstagramPublishUncertain, InstagramVerificationUnavailable,
                                    matching_media, read_account_media, unconfirmed_container)
except ModuleNotFoundError:
    from scripts.instagram_delivery import (InstagramPublishUncertain, InstagramVerificationUnavailable,
                                            matching_media, read_account_media, unconfirmed_container)

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "data" / "social_publish_log.json"

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0").strip() or "v26.0"
TITLE = os.environ.get("POST_TITLE", "").strip()
BODY = os.environ.get("POST_BODY", "").strip()
IMAGE_URL = (os.environ.get("OWN_IMAGE_URL", "").strip() or os.environ.get("POST_IMAGE_URL", "").strip())
SOURCE_NAME = os.environ.get("POST_SOURCE_NAME", "").strip()
ORIGINAL_URL = os.environ.get("POST_ORIGINAL_URL", "").strip()
DO_FACEBOOK = os.environ.get("PUBLISH_FACEBOOK", "false").lower() == "true"
DO_INSTAGRAM = os.environ.get("PUBLISH_INSTAGRAM", "false").lower() == "true"
CONFIRMATION = os.environ.get("PUBLISH_CONFIRMATION", "").strip()
POST_ID = os.environ.get("OWN_POST_ID", "").strip()
POST_URL = (os.environ.get("OWN_POST_URL", "").strip() or os.environ.get("POST_URL", "").strip() or "https://soller-ara.github.io/soller-ara/")


def load_publish_log() -> dict:
    if not LOG_FILE.exists():
        return {"version": 1, "entries": []}
    payload = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list) or any(not isinstance(entry, dict) for entry in payload["entries"]):
        raise ValueError("El registre social no té un format vàlid; no es publica res.")
    return payload


def already_published(log: dict, platform: str) -> bool:
    if not POST_ID:
        return False
    return any(entry.get("post_id") == POST_ID and entry.get("platform") == platform
               and entry.get("status") == "success" for entry in log.get("entries") or [])


def record_result(log: dict, platform: str, status: str, remote_id: str = "", error: str = "", **receipt) -> None:
    entries = log.setdefault("entries", [])
    entries.append({
        "post_id": POST_ID,
        "platform": platform,
        "status": status,
        "remote_id": remote_id,
        "post_url": POST_URL,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        **({"retry_requested": True} if platform == "instagram" and status in
           {"deferred", "publishing", "verification_required"} else {}),
        **receipt,
    })
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
            "User-Agent": "SollerAra-OwnPublisher/0.38",
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
            candidates.append(
                (
                    page_name,
                    page_id,
                    page_token,
                    str(instagram.get("id") or ""),
                    str(instagram.get("username") or ""),
                    page.get("tasks") or [],
                )
            )

    matches = [item for item in candidates if item[0].casefold() in {"soller ara", "sóller ara"}]
    if len(matches) != 1:
        raise RuntimeError("No s'ha pogut identificar de forma única la pàgina Sóller Ara.")

    page_name, page_id, page_token, ig_id, ig_username, tasks = matches[0]
    if DO_FACEBOOK and "CREATE_CONTENT" not in tasks:
        raise RuntimeError("La pàgina Sóller Ara no retorna la tasca CREATE_CONTENT.")
    return page_id, page_token, ig_id, ig_username


def source_reference() -> str:
    return f"\n\nFont original ({SOURCE_NAME or 'Publicació de xarxa'}): {ORIGINAL_URL}" if ORIGINAL_URL else ""


def publish_facebook(page_id: str, page_token: str) -> str:
    message = f"{TITLE}\n\n{BODY}{source_reference()}".strip()
    result = graph(
        f"{page_id}/feed",
        method="POST",
        params={
            "message": message,
            "link": POST_URL,
        },
        token=page_token,
    )
    identifier = str(result.get("post_id") or result.get("id") or "")
    if not identifier:
        raise RuntimeError("Facebook no ha retornat identificador de publicació.")
    print(f"FACEBOOK_OK id={identifier}")
    return identifier


def publish_instagram(ig_id: str, ig_username: str, page_token: str) -> str:
    if ig_username.casefold() != "soller.ara":
        raise RuntimeError("El compte Instagram vinculat no és soller.ara.")
    if not ig_id:
        raise RuntimeError("No s'ha trobat el compte Instagram vinculat a Sóller Ara.")

    log = load_publish_log()
    previous = [entry for entry in log["entries"]
                if entry.get("post_id") == POST_ID and entry.get("platform") == "instagram"]
    confirmed = next((entry for entry in previous
                      if entry.get("status") == "success" and entry.get("remote_id")), None)
    if confirmed:
        return str(confirmed["remote_id"])
    # Also check when the previous runner died before its local log was saved.
    try:
        matches = matching_media(read_account_media(graph, ig_id, TOKEN), POST_URL)
    except Exception as exc:
        raise InstagramVerificationUnavailable(str(exc)) from exc
    if matches:
        remote_id = str(matches[0]["id"])
        print(f"INSTAGRAM_RECONCILED post={POST_ID} media_id={remote_id} copies={len(matches)}")
        return remote_id
    uncertain = unconfirmed_container(previous)
    if uncertain:
        raise InstagramPublishUncertain(
            "Enviament anterior pendent de confirmació; no es crea una altra publicació.",
            str(uncertain.get("container_id") or ""))
    if not IMAGE_URL:
        raise RuntimeError(
            "Instagram necessita una imatge pública. Afegeix POST_IMAGE_URL o desactiva Instagram."
        )

    caption = f"{TITLE}\n\nNotícia completa: {POST_URL}\nEnllaços: https://soller-ara.github.io/soller-ara/enllacos.html\n\n{BODY}{source_reference()}\n\n#Sóller #SollerAra".strip()
    container = graph(
        f"{ig_id}/media",
        method="POST",
        params={"image_url": IMAGE_URL, "caption": caption},
        token=page_token,
    )
    container_id = str(container.get("id") or "")
    if not container_id:
        raise RuntimeError("Instagram no ha retornat identificador de contenidor.")

    for _ in range(12):
        state = graph(
            container_id,
            params={"fields": "status_code,status"},
            token=page_token,
        )
        status = str(state.get("status_code") or "").upper()
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"El contenidor Instagram ha fallat: {status}")
        time.sleep(5)
    else:
        raise RuntimeError("El contenidor Instagram no ha quedat preparat.")

    # Persist intent before the non-idempotent request, including runner crashes.
    record_result(log, "instagram", "publishing", container_id=container_id, stage="media_publish")
    try:
        result = graph(
            f"{ig_id}/media_publish",
            method="POST",
            params={"creation_id": container_id},
            token=page_token,
        )
    except Exception as exc:
        raise InstagramPublishUncertain(str(exc), container_id) from exc
    media_id = str(result.get("id") or "")
    if not media_id:
        raise InstagramPublishUncertain("Instagram no ha retornat identificador de publicació.", container_id)
    print(f"INSTAGRAM_OK account=@{ig_username or '?'} media_id={media_id}")
    return media_id


def main() -> int:
    if CONFIRMATION != "PUBLICAR":
        print("ERROR: cal escriure PUBLICAR.", file=sys.stderr)
        return 2
    if not DO_FACEBOOK and not DO_INSTAGRAM:
        print("No s'ha seleccionat cap xarxa social; no hi ha res a publicar.")
        return 0
    if not TOKEN:
        print("ERROR: falta META_ACCESS_TOKEN.", file=sys.stderr)
        return 2
    if not ORIGINAL_URL and (not TITLE or not BODY):
        print("ERROR: falta títol o text.", file=sys.stderr)
        return 2

    log = load_publish_log()
    pause_value = str((log.get("cooldowns") or {}).get("instagram_until") or "")
    paused = bool(pause_value and datetime.fromisoformat(pause_value.replace("Z", "+00:00")) > datetime.now(timezone.utc))
    facebook_needed = DO_FACEBOOK and not already_published(log, "facebook")
    instagram_needed = DO_INSTAGRAM and not already_published(log, "instagram")
    previous_instagram = [entry for entry in log["entries"]
                          if entry.get("post_id") == POST_ID and entry.get("platform") == "instagram"]
    if instagram_needed and paused and not unconfirmed_container(previous_instagram):
        record_result(log, "instagram", "deferred", error=f"Pausa temporal de Meta fins a {pause_value}. Reintent automàtic pendent.")
        print(f"INSTAGRAM_DEFERRED until={pause_value}")
    if not facebook_needed and (not instagram_needed or paused):
        return 0

    try:
        page_id, page_token, ig_id, ig_username = discover_accounts()
    except Exception as exc:
        print(f"ERROR publicació social: {exc}", file=sys.stderr)
        if facebook_needed:
            record_result(log, "facebook", "error", error=str(exc))
        if instagram_needed and not paused:
            record_result(log, "instagram", "error", error=str(exc))
        return 1

    failed = False

    if DO_FACEBOOK:
        if already_published(log, "facebook"):
            print("FACEBOOK_SKIP: aquesta publicació ja consta com publicada.")
        else:
            try:
                remote_id = publish_facebook(page_id, page_token)
                record_result(log, "facebook", "success", remote_id=remote_id)
            except Exception as exc:
                failed = True
                record_result(log, "facebook", "error", error=str(exc))
                print(f"FACEBOOK_ERROR: {exc}", file=sys.stderr)

    if DO_INSTAGRAM and not paused:
        if already_published(log, "instagram"):
            print("INSTAGRAM_SKIP: aquesta publicació ja consta com publicada.")
        else:
            try:
                remote_id = publish_instagram(ig_id, ig_username, page_token)
                log = load_publish_log()
                record_result(log, "instagram", "success", remote_id=remote_id)
            except Exception as exc:
                log = load_publish_log()
                rate_limited = "application request limit" in str(exc).casefold() and "code=4" in str(exc).casefold()
                if isinstance(exc, (InstagramPublishUncertain, InstagramVerificationUnavailable)):
                    if rate_limited:
                        log.setdefault("cooldowns", {})["instagram_until"] = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
                    uncertain = isinstance(exc, InstagramPublishUncertain)
                    record_result(log, "instagram", "verification_required" if uncertain else "deferred",
                                  error=str(exc), stage="media_publish" if uncertain else "verify",
                                  **({"container_id": exc.container_id} if uncertain else {}))
                    print(f"INSTAGRAM_VERIFY_PENDING post={POST_ID}: {exc}", file=sys.stderr)
                    return 1 if failed or (uncertain and not rate_limited) else 0
                if rate_limited:
                    until = datetime.now(timezone.utc) + timedelta(hours=2)
                    log.setdefault("cooldowns", {})["instagram_until"] = until.isoformat()
                    record_result(log, "instagram", "deferred", error=f"Pausa temporal de Meta fins a {until.isoformat()}. Reintent automàtic pendent. {exc}")
                    print(f"INSTAGRAM_DEFERRED until={until.isoformat()}")
                    return 1 if failed else 0
                failed = True
                record_result(log, "instagram", "error", error=str(exc))
                print(f"INSTAGRAM_ERROR: {exc}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
