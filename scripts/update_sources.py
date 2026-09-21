#!/usr/bin/env python3
"""Actualitza data/posts.json a partir de les fonts públiques configurades.

v0.40: incorpora moderació persistent i control editorial de publicacions.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime, timezone
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "sources.json"
SOCIAL_SOURCES_FILE = ROOT / "social_sources.json"
OUTPUT_FILE = ROOT / "data" / "posts.json"
JS_OUTPUT_FILE = ROOT / "data" / "posts.js"
MANUAL_POSTS_FILE = ROOT / "data" / "manual_posts.json"
MODERATION_FILE = ROOT / "data" / "moderation.json"
MAX_POSTS_PER_SOURCE = 40
SUMMARY_LIMIT = 260
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 SollerAra/0.40"
RELATED_WINDOW_HOURS = 72

CATEGORY_KEYWORDS = {
    "alerts": [
        ("emergències", 8), ("emergencia", 8), ("alerta", 8), ("avís urgent", 8),
        ("avis urgent", 8), ("meteobal", 8), ("112", 8), ("incendi", 7),
        ("inund", 7), ("tempesta", 6), ("pluges", 5), ("precaució", 5),
        ("tall de trànsit", 7), ("tall de transit", 7), ("tall de carretera", 7),
        ("tancament", 5), ("restricció", 5),
    ],
    "services": [
        ("porta a porta", 8), ("recollida", 6), ("recollida selectiva", 8), ("residus", 6), ("deixalleria", 6),
        ("voluminosos", 7), ("reciclatge", 5), ("reciclar", 5),
        ("mobilitat", 5), ("trànsit", 5), ("transit", 5), ("transport", 5),
        ("aparcament", 5), ("estacionament", 5), ("sanejament", 6), ("pluvials", 6),
        ("aigua", 5), ("enllumenat", 5), ("neteja", 5), ("obres", 4),
        ("carretera", 4), ("carrer", 3), ("servei", 3), ("serveis", 3),
    ],
    "culture": [
        ("cultura", 6), ("concert", 7), ("exposició", 7), ("exposicion", 7),
        ("teatre", 7), ("música", 6), ("musica", 6), ("museu", 6),
        ("literari", 6), ("havaneres", 7), ("festa", 5), ("festes", 5),
        ("patrona", 4), ("premis literaris", 7),
    ],
    "sports": [
        ("esport", 6), ("esports", 6), ("futbol", 7), ("bàsquet", 7),
        ("piscina", 6), ("piscines", 6), ("son angelats", 6),
        ("basquet", 7), ("cursa", 7), ("torneig", 7), ("competició", 6),
        ("club esportiu", 6),
    ],
    "commerce": [
        ("comerç", 6), ("comerc", 6), ("comercial", 5), ("horeca", 7),
        ("restauració", 6), ("restauracio", 6), ("mercat", 5), ("empresa", 4),
        ("negoci", 4), ("bons comercials", 7),
    ],
    "agenda": [
        ("agenda", 7), ("reunió informativa", 6), ("reunion informativa", 6),
        ("convocatòria", 6), ("convocatoria", 6), ("tindrà lloc", 6),
        ("tendra lloc", 6), ("inscripció", 5), ("inscripcions", 5),
        ("taller", 5), ("jornada", 5), ("programació", 5), ("programacio", 5),
        ("ple ordinari", 6), ("ple extraordinari", 6),
    ],
}

CATEGORY_PRIORITY = ["alerts", "services", "culture", "sports", "commerce", "agenda", "news"]

NEWS_TITLE_PATTERNS = [
    "detingut", "detenido", "detenida", "detenció", "detencion",
    "robat", "roba ", "robar", "robatori", "robo ", "furt", "hurto",
    "ferit", "ferida", "herido", "herida", "mor ", "muere", "mort ",
    "accident", "accidente", "col·lisió", "colision", "xoc ", "choque",
    "manifestació", "manifestacion", "manifestación", "protesta",
    "massificació", "masificacion", "masificación", "turistificació",
    "turistificacion", "turistificación", "pintades", "pintadas",
]

CULTURE_TITLE_PATTERNS = [
    "art sóller", "art soller", "artista", "artistes", "artistas",
    "exposició", "exposicion", "exposición", "teatre", "teatro",
    "concert", "concierto", "havaneres", "habaneras",
]


DATE_PREFIX_RE = re.compile(
    r"""^\s*(?:
        \d{1,2}[-/][A-Za-zÀ-ÿ]+[-/]\d{4}
        |\d{1,2}[-/]\d{1,2}[-/]\d{2,4}
        |\d{1,2}\s+de\s+[A-Za-zÀ-ÿ]+\s+de\s+\d{4}
    )\s*[-–—:]?\s*""",
    flags=re.I | re.X,
)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def truncate(value: str, limit: int = SUMMARY_LIMIT) -> str:
    if len(value) <= limit:
        return value
    shortened = value[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{shortened}…"


def clean_summary(title: str, summary: str) -> str:
    summary = clean_text(summary)
    title = clean_text(title)

    if title and summary.casefold().startswith(title.casefold()):
        summary = summary[len(title):].lstrip(" :-–—")

    summary = DATE_PREFIX_RE.sub("", summary, count=1)

    if title and summary.casefold().startswith(title.casefold()):
        summary = summary[len(title):].lstrip(" :-–—")

    summary = re.split(r"\s+Documents adjunts\b", summary, maxsplit=1, flags=re.I)[0]
    summary = re.sub(r"\s+", " ", summary).strip(" :-–—")
    return truncate(summary)


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


def category_score(text: str, keywords: list[tuple[str, int]], title: str) -> int:
    score = 0
    title_folded = title.casefold()
    text_folded = text.casefold()
    for keyword, weight in keywords:
        keyword_folded = keyword.casefold()
        if keyword_folded in title_folded:
            score += weight * 3
        elif keyword_folded in text_folded:
            score += weight
    return score


def categorize(title: str, summary: str) -> str:
    title_folded = clean_text(title).casefold()

    # El titular és la senyal més fiable. Evitam que metadades secundàries
    # converteixin successos o protestes en esports/cultura per coincidències accidentals.
    if any(pattern in title_folded for pattern in NEWS_TITLE_PATTERNS):
        return "news"
    if any(pattern in title_folded for pattern in CULTURE_TITLE_PATTERNS):
        return "culture"

    combined = f"{title} {summary}"
    scores = {
        category: category_score(combined, keywords, title)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best_score = max(scores.values(), default=0)
    if best_score <= 0:
        return "news"
    for category in CATEGORY_PRIORITY:
        if scores.get(category, 0) == best_score:
            return category
    return "news"



STOPWORDS = {
    "el", "la", "els", "les", "un", "una", "uns", "unes", "de", "del", "dels",
    "i", "a", "al", "als", "en", "per", "amb", "que", "es", "se", "sa", "ses",
    "aquest", "aquesta", "aquests", "aquestes", "avui", "dema", "soller",
}


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [token for token in value.split() if token not in STOPWORDS and len(token) > 1]
    return " ".join(tokens)


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    sequence = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    union = ta | tb
    jaccard = len(ta & tb) / len(union) if union else 0.0
    return max(sequence, jaccard)


def iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def close_in_time(a: dict, b: dict) -> bool:
    da, db = iso_datetime(a.get("published_at")), iso_datetime(b.get("published_at"))
    if da is None or db is None:
        return normalize_title(a.get("title", "")) == normalize_title(b.get("title", ""))
    return abs((da - db).total_seconds()) <= RELATED_WINDOW_HOURS * 3600


def summary_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    sequence = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    union = ta | tb
    jaccard = len(ta & tb) / len(union) if union else 0.0
    return max(sequence, jaccard)


def is_probably_related(a: dict, b: dict) -> bool:
    if a.get("source_id") == b.get("source_id"):
        return False
    if not close_in_time(a, b):
        return False

    title_score = title_similarity(a.get("title", ""), b.get("title", ""))
    summary_score = summary_similarity(a.get("summary", ""), b.get("summary", ""))

    # Un titular igual no basta: también exigimos similitud clara en el contenido.
    return title_score >= 0.82 and summary_score >= 0.55


def related_source(post: dict) -> dict:
    return {
        "source_id": post.get("source_id"),
        "source": post.get("source"),
        "source_type": post.get("source_type"),
        "url": post.get("url"),
        "published_at": post.get("published_at"),
        "title": post.get("title"),
    }


def annotate_related_posts(posts: list[dict]) -> tuple[list[dict], int]:
    for post in posts:
        post["related_sources"] = []

    relation_count = 0
    for index, post in enumerate(posts):
        for other in posts[index + 1:]:
            if not is_probably_related(post, other):
                continue

            post["related_sources"].append(related_source(other))
            other["related_sources"].append(related_source(post))
            relation_count += 1

    return posts, relation_count


def stable_id(source_id: str, url: str, title: str) -> str:
    raw = f"{source_id}|{url}|{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def text_of(parent: ET.Element, names: list[str]) -> str:
    for name in names:
        found = parent.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def parse_rss(xml_bytes: bytes, source: dict) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items: list[dict] = []

    item_limit = int(source.get("max_items", MAX_POSTS_PER_SOURCE))

    rss_items = root.findall(".//item")
    if rss_items:
        for item in rss_items[:item_limit]:
            title = clean_text(text_of(item, ["title"]))
            url = clean_text(text_of(item, ["link", "guid"]))
            summary = clean_summary(title, text_of(item, ["description", "summary"]))
            published_at = parse_date(text_of(item, ["pubDate", "date", "published", "updated"]))
            if not title or not url:
                continue
            items.append(build_post(source, title, summary, url, published_at))
        return items

    # Atom fallback (namespaces variables segons servidor).
    entries = root.findall(".//{*}entry")
    for entry in entries[:item_limit]:
        title = clean_text(text_of(entry, ["{*}title"]))
        summary = clean_summary(title, text_of(entry, ["{*}summary", "{*}content"]))
        published_at = parse_date(text_of(entry, ["{*}published", "{*}updated"]))
        url = ""
        for link in entry.findall("{*}link"):
            href = link.attrib.get("href", "").strip()
            rel = link.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                url = href
                break
        if not title or not url:
            continue
        items.append(build_post(source, title, summary, url, published_at))
    return items


def build_post(source: dict, title: str, summary: str, url: str, published_at: str | None) -> dict:
    source_type = source.get("source_type", "publisher")
    content_policy = source.get("content_policy", "headline_date_link_only")

    # Política conservadora: dels mitjans de premsa no reproduïm extractes.
    public_summary = ""
    if content_policy == "short_factual_excerpt":
        public_summary = truncate(clean_text(summary), 220)

    post = {
        "id": stable_id(source["id"], url, title),
        "category": source.get("force_category") or categorize(title, summary),
        "source_id": source["id"],
        "source": source["name"],
        "source_type": source_type,
        "language": source.get("language", "ca"),
        "locality": source.get("locality", "Sóller"),
        "published_at": published_at,
        "title": title,
        "summary": public_summary,
        "url": url,
        "platform": source.get("platform"),
        "account": source.get("account"),
        "media_type": source.get("media_type"),
        "content_policy": content_policy,
        "rights_status": source.get("rights_status", "unknown"),
        "image_allowed": source.get("image_policy") == "allowed",
    }
    if source.get("image_policy") == "official_oembed":
        original = urlparse(url)
        source_host = urlparse(str(source.get("url") or "")).netloc.casefold().removeprefix("www.")
        original_host = original.netloc.casefold().removeprefix("www.")
        if original.scheme == "https" and original_host == source_host:
            embed_path = original.path.rstrip("/") + "/embed/"
            post["embed_type"] = "official_oembed"
            post["embed_url"] = original._replace(path=embed_path, query="", fragment="").geturl()
    return post



ARTICLE_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/\d+/[^/?#]+\.html$", re.I)


class LatestArticleLinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self.current_href = urljoin(self.base_url, href)
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_href:
            return

        title = clean_text(" ".join(self.current_text))
        parsed = urlparse(self.current_href)
        if (
            parsed.netloc.endswith("elsoller.cat")
            and ARTICLE_URL_RE.search(parsed.path)
            and len(title) >= 8
        ):
            clean_url = parsed._replace(query="", fragment="").geturl()
            self.links.append((clean_url, title))

        self.current_href = None
        self.current_text = []



class Soller2010LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)
        if not parsed.netloc.endswith("soller2010.com"):
            return
        if not parsed.path.startswith("/noticias/"):
            return
        self.current_href = parsed._replace(query="", fragment="").geturl()
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_href:
            return
        title = clean_text(" ".join(self.current_text))
        self.links.append((self.current_href, title))
        self.current_href = None
        self.current_text = []



class GenericSearchLinkParser(HTMLParser):
    def __init__(self, base_url: str, allowed_host: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.allowed_host = allowed_host.casefold()
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.casefold()
        if host not in {self.allowed_host, f"www.{self.allowed_host}"}:
            return
        if parsed.query or parsed.fragment:
            return
        path = parsed.path.strip("/")
        if not path or "/" in path:
            return
        if path.casefold() in {
            "televisio", "radio", "noticies", "esports", "el-temps",
            "programacio", "contacte", "avis-legal", "privacitat"
        }:
            return
        self.current_href = parsed._replace(query="", fragment="").geturl()
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_href:
            return
        title = clean_text(" ".join(self.current_text))
        if len(title) >= 12:
            self.links.append((self.current_href, title))
        self.current_href = None
        self.current_text = []


class RegexListingLinkParser(HTMLParser):
    def __init__(self, base_url: str, allowed_host: str, article_url_regex: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.allowed_host = allowed_host.casefold()
        self.article_re = re.compile(article_url_regex, re.I)
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.casefold()
        if host not in {self.allowed_host, f"www.{self.allowed_host}"}:
            return
        if not self.article_re.search(parsed.path):
            return
        self.current_href = parsed._replace(query="", fragment="").geturl()
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_href:
            return
        title = clean_text(" ".join(self.current_text))
        if len(title) >= 10:
            self.links.append((self.current_href, title))
        self.current_href = None
        self.current_text = []


class FirstParagraphAfterH1Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_h1 = False
        self.seen_h1 = False
        self.in_p = False
        self.parts: list[str] = []
        self.done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "h1":
            self.in_h1 = True
        elif tag == "p" and self.seen_h1 and not self.done:
            self.in_p = True

    def handle_data(self, data: str) -> None:
        if self.in_p and not self.done:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h1":
            self.in_h1 = False
            self.seen_h1 = True
        elif tag == "p" and self.in_p:
            self.in_p = False
            if clean_text(" ".join(self.parts)):
                self.done = True

    @property
    def paragraph(self) -> str:
        return clean_text(" ".join(self.parts))


class ArticleMetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.in_h1 = False
        self.h1_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()

        if tag == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag == "h1":
            self.in_h1 = True

    def handle_data(self, data: str) -> None:
        if self.in_h1:
            self.h1_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h1":
            self.in_h1 = False

    @property
    def h1(self) -> str:
        return clean_text(" ".join(self.h1_parts))


def fetch_bytes(url: str, accept: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
            return payload, charset
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("No s'ha pogut descarregar la font després de tres intents.")


def fetch_json_bearer(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
            meta_error = body.get("error") or {}
            message = clean_text(str(meta_error.get("message") or "Meta API error"))
            code = meta_error.get("code")
            subcode = meta_error.get("error_subcode")
            error_type = meta_error.get("type")
            details = f"{message} [type={error_type}, code={code}, subcode={subcode}]"
        except Exception:
            details = f"HTTP {exc.code}: resposta de Meta no interpretable"
        raise RuntimeError(details) from exc
    return json.loads(payload.decode("utf-8", errors="replace"))


def social_title_from_text(source_name: str, text: str) -> str:
    category = categorize(text, "")
    labels = {
        "alerts": f"Avís publicat per {source_name}",
        "services": f"Informació de servei de {source_name}",
        "agenda": f"Activitat anunciada per {source_name}",
        "culture": f"Publicació cultural de {source_name}",
        "sports": f"Publicació esportiva de {source_name}",
        "commerce": f"Informació local de {source_name}",
        "news": f"Actualització de {source_name}",
    }
    return labels.get(category, f"Publicació de {source_name}")


def social_summary_from_text(source_name: str, text: str) -> str:
    category = categorize(text, "")
    labels = {
        "alerts": f"{source_name} ha publicat un avís d'interès local. Consulta la publicació original per veure'n tots els detalls.",
        "services": f"{source_name} ha compartit informació relacionada amb un servei o actuació local.",
        "agenda": f"{source_name} ha anunciat una activitat o convocatòria d'interès local.",
        "culture": f"{source_name} ha compartit una publicació relacionada amb cultura o activitats locals.",
        "sports": f"{source_name} ha compartit una actualització relacionada amb l'activitat esportiva.",
        "commerce": f"{source_name} ha compartit informació d'interès per a l'activitat local.",
        "news": f"{source_name} ha publicat una nova actualització relacionada amb Sóller o el seu àmbit de servei.",
    }
    return labels.get(category, f"{source_name} ha publicat una nova actualització.")


def discover_meta_instagram_account(token: str, graph_version: str) -> dict | None:
    """Descobreix la pàgina Sóller Ara i el seu Instagram professional sense exposar tokens."""
    fields = "id,name,instagram_business_account{id,username}"
    endpoint = (
        f"https://graph.facebook.com/{graph_version}/me/accounts?"
        + urlencode({"fields": fields})
    )
    payload = fetch_json_bearer(endpoint, token)
    pages = payload.get("data") or []

    # Prioritat: pàgina Sóller Ara. Si només hi ha una pàgina amb Instagram, usa-la.
    candidates: list[dict] = []
    for page in pages:
        instagram = page.get("instagram_business_account") or {}
        if not instagram.get("id"):
            continue
        candidate = {
            "page_id": page.get("id"),
            "page_name": page.get("name"),
            "ig_user_id": str(instagram.get("id")),
            "username": instagram.get("username"),
        }
        candidates.append(candidate)

    for candidate in candidates:
        if clean_text(candidate.get("page_name")).casefold() in {"soller ara", "sóller ara"}:
            return candidate

    if len(candidates) == 1:
        return candidates[0]

    return None


def validate_meta_own_account(token: str, ig_user_id: str, graph_version: str) -> dict:
    query = urlencode({"fields": "id,username,media_count"})
    endpoint = f"https://graph.facebook.com/{graph_version}/{ig_user_id}?{query}"
    payload = fetch_json_bearer(endpoint, token)

    media_query = urlencode({
        "fields": "id,caption,media_type,permalink,timestamp",
        "limit": 5,
    })
    media_endpoint = f"https://graph.facebook.com/{graph_version}/{ig_user_id}/media?{media_query}"
    media_payload = fetch_json_bearer(media_endpoint, token)

    return {
        "id": str(payload.get("id") or ""),
        "username": payload.get("username"),
        "media_count": payload.get("media_count"),
        "sample_media_count": len(media_payload.get("data") or []),
    }


def fetch_meta_instagram_source(source: dict, token: str, ig_user_id: str, graph_version: str) -> list[dict]:
    username = str(source.get("username") or source.get("account") or "").lstrip("@").strip()
    if not username:
        return []

    fields = (
        f"business_discovery.username({username})"
        "{username,name,media.limit(20){id,caption,media_type,permalink,timestamp}}"
    )
    query = urlencode({"fields": fields})
    endpoint = f"https://graph.facebook.com/{graph_version}/{ig_user_id}?{query}"
    payload = fetch_json_bearer(endpoint, token)
    business = payload.get("business_discovery") or {}
    media = ((business.get("media") or {}).get("data")) or []

    source_id = f"instagram-{username}"
    source_name = source.get("name") or business.get("name") or username
    account = source.get("account") or f"@{username}"
    posts: list[dict] = []

    for item in media:
        permalink = clean_text(item.get("permalink"))
        published_at = parse_date(item.get("timestamp"))
        caption = clean_text(item.get("caption"))
        if not permalink or not published_at:
            continue

        category = categorize(caption, "")
        media_type = str(item.get("media_type") or "").casefold()
        posts.append({
            "id": stable_id(source_id, permalink, str(item.get("id") or permalink)),
            "category": category,
            "source_id": source_id,
            "source": source_name,
            "source_type": "social",
            "language": source.get("language", "ca"),
            "locality": source.get("locality", "Sóller"),
            "published_at": published_at,
            "title": social_title_from_text(source_name, caption),
            "summary": social_summary_from_text(source_name, caption),
            "url": permalink,
            "platform": "Instagram",
            "account": account,
            "media_type": "video" if media_type in {"video", "reels", "reel"} else "image",
            "content_policy": "generated_social_summary",
            "rights_status": "platform_embed",
            "image_allowed": False,
        })

    pseudo_source = {"max_age_days": source.get("max_age_days", 30)}
    return filter_by_max_age(pseudo_source, posts)


def fetch_optional_meta_social_sources() -> tuple[list[dict], list[dict], list[dict]]:
    if not SOCIAL_SOURCES_FILE.exists():
        return [], [], []

    config = json.loads(SOCIAL_SOURCES_FILE.read_text(encoding="utf-8"))
    targets = [
        source for source in config.get("sources", [])
        if source.get("mode") == "meta_business_discovery"
    ]
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("META_IG_USER_ID", "").strip()
    graph_version = os.environ.get("META_GRAPH_VERSION", "v26.0").strip() or "v26.0"

    integration_status: list[dict] = []
    source_status: list[dict] = []
    posts: list[dict] = []

    if not token:
        for source in targets:
            integration_status.append({
                "platform": "Instagram",
                "name": source.get("name"),
                "account": source.get("account"),
                "configured": False,
                "ok": False,
                "count": 0,
                "status": "token_required",
                "error": None,
            })
        return posts, source_status, integration_status

    discovery: dict | None = None
    if not ig_user_id:
        try:
            discovery = discover_meta_instagram_account(token, graph_version)
            if discovery:
                ig_user_id = discovery["ig_user_id"]
                print(
                    "META_DISCOVERY OK "
                    f"page={discovery.get('page_name')} "
                    f"instagram=@{discovery.get('username') or '?'} "
                    f"ig_user_id={ig_user_id}"
                )
            else:
                print(
                    "META_DISCOVERY sense resultat: no s'ha trobat una única pàgina Sóller Ara amb Instagram.",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"META_DISCOVERY ERROR: {exc}", file=sys.stderr)

    if not ig_user_id:
        for source in targets:
            integration_status.append({
                "platform": "Instagram",
                "name": source.get("name"),
                "account": source.get("account"),
                "configured": False,
                "ok": False,
                "count": 0,
                "status": "ig_user_id_discovery_required",
                "error": None,
            })
        return posts, source_status, integration_status

    try:
        own = validate_meta_own_account(token, ig_user_id, graph_version)
        print(
            "META_OWN_ACCOUNT OK "
            f"instagram=@{own.get('username') or '?'} "
            f"media_count={own.get('media_count')} "
            f"sample_media_count={own.get('sample_media_count')}"
        )
    except Exception as exc:
        print(f"META_OWN_ACCOUNT ERROR: {exc}", file=sys.stderr)

    for source in targets:
        source_id = f"instagram-{str(source.get('username') or source.get('account') or '').lstrip('@')}"
        try:
            source_posts = fetch_meta_instagram_source(source, token, ig_user_id, graph_version)
            posts.extend(source_posts)
            status = {
                "source_id": source_id,
                "name": source.get("name"),
                "source_type": "social",
                "method": "meta_business_discovery",
                "ok": True,
                "count": len(source_posts),
                "error": None,
            }
            source_status.append(status)
            integration_status.append({
                "platform": "Instagram",
                "name": source.get("name"),
                "account": source.get("account"),
                "configured": True,
                "ok": True,
                "count": len(source_posts),
                "status": "active",
                "error": None,
            })
            print(f"OK {source.get('name')}: {len(source_posts)} publicacions Instagram")
        except Exception as exc:
            error_text = str(exc)
            source_status.append({
                "source_id": source_id,
                "name": source.get("name"),
                "source_type": "social",
                "method": "meta_business_discovery",
                "ok": False,
                "count": 0,
                "error": error_text,
            })
            integration_status.append({
                "platform": "Instagram",
                "name": source.get("name"),
                "account": source.get("account"),
                "configured": True,
                "ok": False,
                "count": 0,
                "status": "error",
                "error": error_text,
            })
            print(f"ERROR {source.get('name')}: {exc}", file=sys.stderr)

    return posts, source_status, integration_status


def date_from_article_url(url: str) -> str | None:
    match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if not match:
        return None
    try:
        year, month, day = map(int, match.groups())
        return datetime(year, month, day, 12, 0, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None



def fetch_html_search(source: dict) -> list[dict]:
    payload, charset = fetch_bytes(
        source["url"],
        "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    )
    listing_html = payload.decode(charset, errors="replace")
    allowed_host = source.get("allowed_host") or urlparse(source["url"]).netloc
    parser = GenericSearchLinkParser(source["url"], str(allowed_host).removeprefix("www."))
    parser.feed(listing_html)

    unique_links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in parser.links:
        if url in seen:
            continue
        seen.add(url)
        unique_links.append((url, title))

    max_items = int(source.get("max_items", 30))
    posts: list[dict] = []

    for url, listing_title in unique_links[:max_items]:
        title = listing_title
        summary = ""
        published_at = None

        try:
            article_payload, article_charset = fetch_bytes(
                url,
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            )
            article_html = article_payload.decode(article_charset, errors="replace")
            meta = ArticleMetaParser()
            meta.feed(article_html)

            title = clean_text(
                meta.meta.get("og:title")
                or meta.meta.get("twitter:title")
                or meta.h1
                or listing_title
            )
            if source.get("id") == "tib-avisos-soller":
                title = re.sub(r"^TIB\s*-\s*Aviso:\s*", "", title, flags=re.I)
                title = re.sub(r"\s*-\s*CTM\s*$", "", title, flags=re.I)
            if source.get("id") == "consell-mallorca-soller":
                title = re.sub(r"\s+-\s+www\s+-\s+LIVE\s+[\d.]+\s*$", "", title, flags=re.I)
            summary = clean_summary(
                title,
                meta.meta.get("description")
                or meta.meta.get("og:description")
                or meta.meta.get("twitter:description")
                or "",
            )
            visible_text = clean_text(article_html)
            published_at = (
                parse_date(meta.meta.get("article:published_time"))
                or parse_date(meta.meta.get("datepublished"))
                or parse_date(meta.meta.get("date"))
                or parse_numeric_date_from_text(visible_text)
            )
        except Exception as exc:
            print(f"AVÍS {source['name']} article {url}: {exc}", file=sys.stderr)

        if not title or not published_at:
            continue

        posts.append(build_post(source, title, summary, url, published_at))

    return posts


def fetch_html_listing_regex(source: dict) -> list[dict]:
    allowed_host = str(source.get("allowed_host") or urlparse(source["url"]).netloc).removeprefix("www.")
    article_url_regex = str(source.get("article_url_regex") or r".+")

    listing_urls = [source["url"]]
    template = source.get("listing_url_template")
    try:
        page_count = max(1, int(source.get("listing_pages", 1)))
    except (TypeError, ValueError):
        page_count = 1
    if template and page_count > 1:
        listing_urls.extend(str(template).format(page=page) for page in range(2, page_count + 1))

    candidate_links: list[tuple[str, str]] = []
    for listing_url in listing_urls:
        payload, charset = fetch_bytes(
            listing_url,
            "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        )
        listing_html = payload.decode(charset, errors="replace")
        parser = RegexListingLinkParser(listing_url, allowed_host, article_url_regex)
        parser.feed(listing_html)
        candidate_links.extend(parser.links)

        # Fallback per portals Liferay amb HTML poc convencional.
        raw_hrefs = re.findall(r'''href=["']([^"']+)["']''', listing_html, flags=re.I)
        for href in raw_hrefs:
            absolute = urljoin(listing_url, html.unescape(href))
            parsed_candidate = urlparse(absolute)
            host = parsed_candidate.netloc.casefold()
            if host not in {allowed_host.casefold(), f"www.{allowed_host.casefold()}"}:
                continue
            if not re.search(article_url_regex, parsed_candidate.path, flags=re.I):
                continue
            clean_candidate = parsed_candidate._replace(query="", fragment="").geturl()
            candidate_links.append((clean_candidate, ""))

    unique_links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in candidate_links:
        if url in seen:
            continue
        seen.add(url)
        unique_links.append((url, title))

    prefilter = [
        clean_text(str(keyword)).casefold()
        for keyword in source.get("prefilter_url_keywords", [])
        if clean_text(str(keyword))
    ]
    if prefilter:
        unique_links = [
            (url, title) for url, title in unique_links
            if any(keyword in url.casefold() for keyword in prefilter)
        ]

    if source.get("diagnostic_links"):
        for candidate_url, candidate_title in unique_links[:40]:
            print(
                f"MATCHED_LINK {source.get('id')}: {candidate_url} | title={candidate_title}",
                file=sys.stderr,
            )

    max_items = int(source.get("max_items", 30))
    posts: list[dict] = []

    for url, listing_title in unique_links[:max_items]:
        title = listing_title
        summary = ""
        published_at = date_from_article_url(url)

        try:
            article_payload, article_charset = fetch_bytes(
                url,
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            )
            article_html = article_payload.decode(article_charset, errors="replace")
            meta = ArticleMetaParser()
            meta.feed(article_html)

            title = clean_text(
                meta.meta.get("og:title")
                or meta.meta.get("twitter:title")
                or meta.h1
                or listing_title
            )

            if source.get("id") == "tib-avisos-soller":
                if meta.h1:
                    title = clean_text(meta.h1)
                title = re.sub(r"^TIB\s*-\s*Aviso:\s*", "", title, flags=re.I)
                title = re.sub(r"\s*-\s*CTM\s*$", "", title, flags=re.I)

            if source.get("id") == "consell-mallorca-soller":
                title = re.sub(r"\s+-\s+www\s+-\s+LIVE\s+[\d.]+\s*$", "", title, flags=re.I)

            summary = clean_summary(
                title,
                meta.meta.get("description")
                or meta.meta.get("og:description")
                or meta.meta.get("twitter:description")
                or "",
            )

            if source.get("extract_first_paragraph"):
                body_parser = FirstParagraphAfterH1Parser()
                body_parser.feed(article_html)
                if body_parser.paragraph:
                    summary = clean_summary(title, body_parser.paragraph)

            published_at = (
                parse_date(meta.meta.get("article:published_time"))
                or parse_date(meta.meta.get("datepublished"))
                or parse_date(meta.meta.get("date"))
                or published_at
                or parse_numeric_date_from_text(clean_text(article_html))
            )
        except Exception as exc:
            print(f"AVÍS {source['name']} article {url}: {exc}", file=sys.stderr)

        if not title or not published_at:
            continue

        if source.get("diagnostic_links"):
            print(
                f"PARSED_ITEM {source.get('id')}: {published_at} | {title} | {url}",
                file=sys.stderr,
            )

        posts.append(build_post(source, title, summary, url, published_at))

    return posts


def fetch_html_latest(source: dict) -> list[dict]:
    payload, charset = fetch_bytes(source["url"], "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    html_text = payload.decode(charset, errors="replace")

    listing = LatestArticleLinkParser(source["url"])
    listing.feed(html_text)

    unique_links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in listing.links:
        if url in seen:
            continue
        seen.add(url)
        unique_links.append((url, title))

    max_items = int(source.get("max_items", 20))
    posts: list[dict] = []

    for url, listing_title in unique_links[:max_items]:
        title = listing_title
        summary = ""
        published_at = date_from_article_url(url)

        try:
            article_payload, article_charset = fetch_bytes(
                url,
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            )
            article_html = article_payload.decode(article_charset, errors="replace")
            parser = ArticleMetaParser()
            parser.feed(article_html)

            title = clean_text(
                parser.meta.get("og:title")
                or parser.meta.get("twitter:title")
                or parser.h1
                or listing_title
            )
            summary = clean_summary(
                title,
                parser.meta.get("description")
                or parser.meta.get("og:description")
                or parser.meta.get("twitter:description")
                or "",
            )
            published_at = (
                parse_date(parser.meta.get("article:published_time"))
                or parse_date(parser.meta.get("datepublished"))
                or parse_date(parser.meta.get("date"))
                or published_at
            )
        except Exception as exc:
            print(f"AVÍS {source['name']} article {url}: {exc}", file=sys.stderr)

        if not title:
            continue
        posts.append(build_post(source, title, summary, url, published_at))

    return posts



def parse_numeric_date_from_text(value: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", value)
    if not match:
        return None
    try:
        day, month, year = map(int, match.groups())
        return datetime(year, month, day, 12, 0, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def fetch_soller2010_news(source: dict) -> list[dict]:
    payload, charset = fetch_bytes(
        source["url"],
        "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    )
    listing_html = payload.decode(charset, errors="replace")
    parser = Soller2010LinkParser(source["url"])
    parser.feed(listing_html)

    unique_links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in parser.links:
        if url in seen:
            continue
        seen.add(url)
        unique_links.append((url, title))

    max_items = int(source.get("max_items", 15))
    posts: list[dict] = []

    for url, listing_title in unique_links[:max_items]:
        title = listing_title if len(listing_title) > 5 and listing_title.casefold() != "veure" else ""
        summary = ""
        published_at = None

        try:
            article_payload, article_charset = fetch_bytes(
                url,
                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            )
            article_html = article_payload.decode(article_charset, errors="replace")
            meta = ArticleMetaParser()
            meta.feed(article_html)

            title = clean_text(
                meta.meta.get("og:title")
                or meta.meta.get("twitter:title")
                or meta.h1
                or listing_title
            )
            title = re.sub(r"\s+Darrers avisos\s*$", "", title, flags=re.I).strip()

            summary = clean_summary(
                title,
                meta.meta.get("description")
                or meta.meta.get("og:description")
                or meta.meta.get("twitter:description")
                or "",
            )
            if summary.casefold() in {"soller 2010", "sóller 2010"}:
                summary = ""
            visible_text = clean_text(article_html)
            published_at = (
                parse_date(meta.meta.get("article:published_time"))
                or parse_date(meta.meta.get("datepublished"))
                or parse_date(meta.meta.get("date"))
                or parse_numeric_date_from_text(visible_text)
            )
        except Exception as exc:
            print(f"AVÍS {source['name']} article {url}: {exc}", file=sys.stderr)

        # No publiquem un avís sense data: és preferible ometre'l que presentar-lo com a recent.
        if not title or not published_at:
            continue

        posts.append(build_post(source, title, summary, url, published_at))

    return posts


def fetch_aemet_alerts(source: dict) -> list[dict]:
    payload, _ = fetch_bytes(
        source["url"],
        "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    )
    posts = parse_rss(payload, source)
    zone_codes = [str(code) for code in source.get("filter_zone_codes", [])]

    filtered: list[dict] = []
    for post in posts:
        haystack = f"{post.get('title', '')} {post.get('summary', '')} {post.get('url', '')}"
        if zone_codes and not any(code in haystack for code in zone_codes):
            continue
        post["category"] = "alerts"
        filtered.append(post)

    return filtered


def social_summary_from_title(source: dict, title: str) -> str:
    name = source.get("name", "la font")
    lowered = title.casefold()

    if source.get("id") == "youtube-ajuntament-soller" and re.search(
        r"\bple\b|\bsessi[oó] plen[aà]ria\b", lowered
    ):
        return f"Vídeo publicat per {name} relacionat amb una sessió plenària o activitat municipal."
    if re.search(r"\bdirecte\b|\blive\b", lowered):
        return f"Retransmissió publicada per {name}."

    # Una paraula parcial (p. ex. "completa") no acredita una sessió municipal.
    # L'autoria és l'única informació que afirmam per defecte.
    return f"Vídeo publicat per {name}."


def fetch_youtube_channel(source: dict) -> list[dict]:
    payload, _ = fetch_bytes(
        source["url"],
        "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    )
    posts = parse_rss(payload, source)
    max_items = int(source.get("max_items", 15))

    for post in posts[:max_items]:
        post["source_type"] = "social"
        post["platform"] = source.get("platform", "YouTube")
        post["account"] = source.get("account")
        post["media_type"] = "video"
        post["summary"] = social_summary_from_title(source, post.get("title", ""))
    return posts[:max_items]


def fetch_freenewsapi_search(source: dict) -> list[dict]:
    endpoint = source.get("url", "https://freenewsapi.ai/v1/search")
    host = clean_text(source.get("host"))
    query_terms = [
        clean_text(str(term))
        for term in source.get("query_terms", [])
        if clean_text(str(term))
    ]
    if not host or not query_terms:
        return []

    max_items = int(source.get("max_items", 25))
    seen_urls: set[str] = set()
    posts: list[dict] = []

    for term in query_terms:
        query = urlencode({
            "host": host,
            "q": term,
            "size": max_items,
            "fields": "title,url,published_at,lang",
        })
        payload, _ = fetch_bytes(
            f"{endpoint}?{query}",
            "application/json, text/plain;q=0.9, */*;q=0.8",
        )
        parsed = json.loads(payload.decode("utf-8", errors="replace"))

        for item in parsed.get("results", []):
            title = clean_text(item.get("title"))
            url = clean_text(item.get("url"))
            published_at = parse_date(item.get("published_at"))
            if not title or not url or not published_at or url in seen_urls:
                continue
            if urlparse(url).netloc.casefold() != host.casefold():
                continue
            seen_urls.add(url)
            posts.append(build_post(source, title, "", url, published_at))

    posts.sort(key=sort_key, reverse=True)
    return posts[: max_items * max(1, len(query_terms))]


def fetch_source(source: dict) -> list[dict]:
    if source["type"] in ("rss", "atom"):
        payload, _ = fetch_bytes(
            source["url"],
            "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        )
        return parse_rss(payload, source)

    if source["type"] == "html_latest":
        return fetch_html_latest(source)

    if source["type"] == "html_search":
        return fetch_html_search(source)

    if source["type"] == "html_listing_regex":
        return fetch_html_listing_regex(source)

    if source["type"] == "freenewsapi_search":
        return fetch_freenewsapi_search(source)

    if source["type"] == "soller2010_news":
        return fetch_soller2010_news(source)

    if source["type"] == "aemet_alerts":
        return fetch_aemet_alerts(source)

    if source["type"] == "youtube_channel":
        return fetch_youtube_channel(source)

    raise ValueError(f"Tipus de font no suportat: {source['type']}")




def filter_by_keywords(source: dict, posts: list[dict]) -> list[dict]:
    """Filtra una font general perquè només entrin elements rellevants per Sóller."""
    keywords = [
        unicodedata.normalize("NFC", clean_text(str(keyword))).casefold()
        for keyword in source.get("include_keywords", [])
        if clean_text(str(keyword))
    ]
    if not keywords:
        return posts

    filtered: list[dict] = []
    for post in posts:
        # El resum de YouTube es genera amb el nom de la font. Aquest nom
        # no pot convertir un vídeo aliè a Sóller en una coincidència local.
        fields = ["title"] if source.get("type") == "youtube_channel" else ["title", "summary", "url"]
        haystack = unicodedata.normalize("NFC", " ".join(
            str(post.get(field) or "") for field in fields
        )).casefold()
        if any(keyword in haystack for keyword in keywords):
            filtered.append(post)
    return filtered

def sort_key(post: dict) -> float:
    published = iso_datetime(post.get("published_at"))
    if published is None:
        return float("-inf")
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published.astimezone(timezone.utc).timestamp()


def filter_by_max_age(source: dict, posts: list[dict]) -> list[dict]:
    max_age_days = source.get("max_age_days")
    if max_age_days is None:
        return posts

    try:
        max_age_days = int(max_age_days)
    except (TypeError, ValueError):
        return posts

    now = datetime.now(timezone.utc)
    filtered: list[dict] = []

    for post in posts:
        published = iso_datetime(post.get("published_at"))
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        age_days = (now - published.astimezone(timezone.utc)).total_seconds() / 86400
        if 0 <= age_days <= max_age_days:
            filtered.append(post)

    return filtered


def load_moderation() -> dict:
    if not MODERATION_FILE.exists():
        return {}
    try:
        payload = json.loads(MODERATION_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"ERROR moderació: {exc}", file=sys.stderr)
        return {}


def load_hidden_post_ids() -> set[str]:
    payload = load_moderation()
    return {
        str(item) for item in (payload.get("hidden_post_ids") or [])
        if str(item).strip()
    }


def load_category_overrides() -> dict[str, str]:
    raw = load_moderation().get("category_overrides") or {}
    allowed = {"news", "agenda", "alerts", "services", "culture", "sports", "commerce"}
    return {str(post_id): str(category) for post_id, category in raw.items() if str(post_id).strip() and str(category) in allowed}


def load_manual_posts() -> list[dict]:
    if not MANUAL_POSTS_FILE.exists():
        return []
    try:
        payload = json.loads(MANUAL_POSTS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR publicacions pròpies: {exc}", file=sys.stderr)
        return []

    posts = []
    for item in payload.get("posts") or []:
        if not item.get("id") or not item.get("title") or not item.get("published_at"):
            continue
        post = dict(item)
        post.setdefault("source_id", "soller-ara")
        post.setdefault("source", "Sóller Ara")
        post.setdefault("source_type", "own")
        post.setdefault("language", "ca")
        post.setdefault("locality", "Sóller")
        post.setdefault("category", "news")
        post.setdefault("content_policy", "owned_content")
        post.setdefault("rights_status", "owned")
        posts.append(post)
    return posts


def load_disabled_source_posts(sources: list[dict]) -> list[dict]:
    """Conserva entrades ja recopilades, sense consultar les fonts desactivades."""
    disabled = [source for source in sources if not source.get("enabled", True)]
    if not disabled or not OUTPUT_FILE.exists():
        return []

    # Si el fitxer anterior és il·legible, aturam abans de sobreescriure'l.
    payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    previous = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(previous, list) or any(not isinstance(post, dict) for post in previous):
        raise ValueError("El fitxer anterior de publicacions no té un format vàlid.")

    retained: list[dict] = []
    for source in disabled:
        source_posts = [post for post in previous if post.get("source_id") == source.get("id")]
        source_posts = filter_by_keywords(source, source_posts)
        retention = {"max_age_days": source.get("max_age_days", 60)}
        retained.extend(filter_by_max_age(retention, source_posts))
    return retained


def main() -> int:
    config = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    posts = load_disabled_source_posts(config.get("sources", []))
    errors: list[dict] = []
    source_status: list[dict] = []
    social_integration_status: list[dict] = []

    for source in config.get("sources", []):
        if not source.get("enabled", True):
            continue
        try:
            source_posts = fetch_source(source)
            source_posts = filter_by_keywords(source, source_posts)
            source_posts = filter_by_max_age(source, source_posts)
            posts.extend(source_posts)
            source_status.append({
                "source_id": source.get("id"),
                "name": source.get("name"),
                "source_type": source.get("source_type", "publisher"),
                "method": source.get("type"),
                "ok": True,
                "count": len(source_posts),
                "error": None,
            })
            print(f"OK {source['name']}: {len(source_posts)} publicacions")
        except Exception as exc:  # Es registra l'error sense impedir altres fonts.
            errors.append({"source_id": source.get("id"), "error": str(exc)})
            source_status.append({
                "source_id": source.get("id"),
                "name": source.get("name"),
                "source_type": source.get("source_type", "publisher"),
                "method": source.get("type"),
                "ok": False,
                "count": 0,
                "error": str(exc),
            })
            print(f"ERROR {source.get('name', source.get('id'))}: {exc}", file=sys.stderr)

    manual_posts = load_manual_posts()
    posts.extend(manual_posts)
    if manual_posts:
        source_status.append({
            "source_id": "soller-ara",
            "name": "Sóller Ara",
            "source_type": "own",
            "method": "manual",
            "ok": True,
            "count": len(manual_posts),
            "error": None,
        })
        print(f"OK Sóller Ara: {len(manual_posts)} publicacions pròpies")

    meta_posts, meta_source_status, social_integration_status = fetch_optional_meta_social_sources()
    posts.extend(meta_posts)
    # Les integracions socials opcionals només entren a la salut general quan funcionen.
    # Els errors/pending es documenten a social_integration_status sense fer aparèixer
    # les sis fonts estables com a caigudes.
    source_status.extend(status for status in meta_source_status if status.get("ok"))

    # Només elimina duplicats exactes de la mateixa entrada. Mai elimina una publicació d'una altra font.
    hidden_post_ids = load_hidden_post_ids()
    category_overrides = load_category_overrides()
    for post in posts:
        override = category_overrides.get(str(post.get("id") or ""))
        if override:
            post["category"] = override
    deduped = {
        post["id"]: post for post in posts
        if post.get("id") not in hidden_post_ids
    }
    ordered_posts = sorted(deduped.values(), key=sort_key, reverse=True)
    ordered_posts, related_pair_count = annotate_related_posts(ordered_posts)

    payload = {
        "version": 41,
        "generator_version": "0.59",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(source_status),
        "source_status": source_status,
        "social_integration_status": social_integration_status,
        "post_count": len(ordered_posts),
        "related_pair_count": related_pair_count,
        "errors": errors,
        "posts": ordered_posts,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    OUTPUT_FILE.write_text(json_payload + "\n", encoding="utf-8")
    JS_OUTPUT_FILE.write_text(
        "window.SOLLER_ARA_DATA = " + json_payload + ";\n",
        encoding="utf-8",
    )

    if not ordered_posts:
        print("No s'ha obtingut cap publicació; es conserva un JSON vàlid però buit.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
