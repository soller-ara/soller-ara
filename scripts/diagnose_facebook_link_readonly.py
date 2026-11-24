#!/usr/bin/env python3
"""Compare manual links with GET requests only. Never publish, scrape or edit.

Run on a diagnostic branch, not inside the publishing workflow. The only local
write is the Actions job summary. Tokens and source photographs are not saved.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
PAGE_ID = "1384755221378998"
GRAPH_VERSION = "v26.0"
POST_IDS = (
    "soller-ara-e6264aa37e94badb", "soller-ara-dddecc17dad9776d",
    "soller-ara-711a34916e298494", "soller-ara-e175d2cb5467d844",
)
MAX_RESPONSE = 1048576


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def clean_url(value: str) -> str:
    parsed = urlparse(str(value or ""))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def graph_get(path: str, params: dict, token: str) -> dict:
    if path not in {"", "me/accounts", "me/permissions"} and not re.fullmatch(
            rf"{PAGE_ID}_[0-9]+(?:/attachments)?", path):
        raise ValueError("Diagnostic graph path not allowed")
    if not token:
        return {"ok": False, "error": {"message": "Token unavailable"}}
    query = urlencode(params)
    request = Request(f"https://graph.facebook.com/{GRAPH_VERSION}/{path}?{query}",
                      method="GET", headers={"Authorization": f"Bearer {token}",
                      "Accept": "application/json", "User-Agent": "SollerAra-LinkDiagnostic/1.0"})
    # Refuse redirects so the Authorization header never reaches another host.
    try:
        with build_opener(NoRedirect()).open(request, timeout=25) as response:
            return {"ok": True, "http_status": response.status,
                    "data": json.loads(response.read(MAX_RESPONSE).decode("utf-8"))}
    except HTTPError as exc:
        try:
            error = (json.loads(exc.read(MAX_RESPONSE).decode("utf-8")) or {}).get("error") or {}
        except (ValueError, AttributeError):
            error = {"message": "Non-JSON HTTP rejection"}
        message = str(error.get("message") or "HTTP rejection").replace(token, "[redacted]")
        return {"ok": False, "http_status": exc.code, "error": {
            k: error.get(k) for k in ("type", "code", "error_subcode", "is_transient", "fbtrace_id")
            if k in error} | {"message": message[:600]}}
    except (URLError, TimeoutError, ValueError) as exc:
        return {"ok": False, "error": {"message": type(exc).__name__}}


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.canonical = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key in {"og:url", "og:type", "og:title", "og:image"}:
                self.meta[key] = attrs.get("content") or ""
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href") or ""


def public_metadata(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.instagram.com" or not re.fullmatch(
            r"/p/[A-Za-z0-9_-]+/", parsed.path):
        raise ValueError("Diagnostic public URL not allowed")
    request = Request(url, method="GET", headers={
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "Range": "bytes=0-524288", "Accept": "text/html"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            parser = Metadata()
            parser.feed(response.read(524288).decode("utf-8", errors="replace"))
            image = parser.meta.get("og:image") or ""
            return {"http_status": response.status, "canonical": clean_url(parser.canonical),
                    "og_url": clean_url(parser.meta.get("og:url") or ""),
                    "og_type": parser.meta.get("og:type"),
                    "og_title": (parser.meta.get("og:title") or "")[:180],
                    "has_image": bool(image), "image_host": urlparse(image).hostname}
    except HTTPError as exc:
        return {"http_status": exc.code, "redirect": clean_url(exc.headers.get("Location") or "")}
    except (URLError, TimeoutError) as exc:
        return {"error": type(exc).__name__}


def attachment_summary(item: dict) -> dict:
    image = ((item.get("media") or {}).get("image") or {})
    return {"type": item.get("type"), "media_type": item.get("media_type"),
            "title": str(item.get("title") or "")[:180],
            "target_url": clean_url((item.get("target") or {}).get("url") or item.get("url") or ""),
            "has_image": bool(image.get("src")), "image_host": urlparse(image.get("src") or "").hostname,
            "image_size": [image.get("width"), image.get("height")],
            "children": [attachment_summary(child) for child in (item.get("subattachments") or {}).get("data", [])]}


def safe_json(payload, secrets: tuple[str, ...], *, indent=None) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=indent)
    for secret in secrets:
        if secret:
            encoded = encoded.replace(secret, "[redacted]")
    return encoded


def main() -> int:
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not token:
        print("DIAGNOSTIC_ERROR: META_ACCESS_TOKEN unavailable")
        return 2
    manual = json.loads((ROOT / "data/manual_posts.json").read_text())["posts"]
    entries = json.loads((ROOT / "data/social_publish_log.json").read_text())["entries"]
    permissions = graph_get("me/permissions", {}, token)
    granted = [p.get("permission") for p in (permissions.get("data") or {}).get("data", [])
               if p.get("status") == "granted"]
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "permissions": granted if permissions.get("ok") else permissions, "cases": []}
    accounts = graph_get("me/accounts", {"fields": "id,name,access_token,tasks"}, token)
    pages = [p for p in (accounts.get("data") or {}).get("data", [])
             if str(p.get("id")) == PAGE_ID and str(p.get("name") or "").casefold() in {"sóller ara", "soller ara"}]
    if len(pages) != 1:
        print("DIAGNOSTIC_ACCOUNT_ERROR " + json.dumps({
            "ok": accounts.get("ok"), "error": accounts.get("error"), "matches": len(pages)}))
        return 1
    page = pages[0]
    page_token = str(page.get("access_token") or "")
    report["page"] = {"id": PAGE_ID, "name": page["name"], "tasks": page.get("tasks")}
    for identifier in POST_IDS:
        post = next(p for p in manual if p.get("id") == identifier)
        url = post["original_url"]
        history = [e for e in entries if e.get("post_id") == identifier and e.get("platform") == "facebook"]
        case = {"post_id": identifier, "created_at": post.get("published_at"), "original_url": url,
                "history": [{k: e.get(k) for k in ("status", "remote_id", "error", "recorded_at")} for e in history],
                "urls": []}
        for label, reference in (("submitted", url), ("canonical", clean_url(url))):
            node = graph_get("", {"id": reference, "fields": "id,og_object{id,type,title,updated_time}"}, token)
            case["urls"].append({"variant": label, "url": reference, "graph": node,
                                 "public_metadata": public_metadata(reference)})
        receipt = next((e for e in history if e.get("status") == "success" and e.get("remote_id")), None)
        if receipt:
            remote_id = str(receipt["remote_id"])
            case["facebook_post"] = graph_get(remote_id, {
                "fields": "id,created_time,permalink_url,is_published,is_hidden"}, page_token)
            attachments = graph_get(remote_id + "/attachments", {
                "fields": "type,media_type,title,url,target,media,subattachments"}, page_token)
            case["facebook_attachments"] = ([attachment_summary(item) for item in
                (attachments.get("data") or {}).get("data", [])] if attachments.get("ok") else attachments)
        report["cases"].append(case)
        # Print each result before continuing, so a provider timeout leaves evidence.
        print("LINK_DIAGNOSTIC " + safe_json(case, (token, page_token)), flush=True)
    # Only the diagnostic result reaches logs; neither account tokens nor images do.
    encoded = safe_json(report, (token, page_token), indent=2)
    print("DIAGNOSTIC_SUMMARY " + safe_json({k: v for k, v in report.items() if k != "cases"}, (token, page_token)))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).write_text("# Diagnóstico de enlaces · solo lectura\n\n```json\n" + encoded + "\n```\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
