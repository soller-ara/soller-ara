"""Bounded text preparation from permitted data, with no network or model calls."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

SITE_URL = "https://soller-ara.github.io/soller-ara/"
SITE_LABEL = f"Sóller Ara · {SITE_URL}"
INSTAGRAM_CAPTION_LIMIT = 2200
SUMMARY_POLICIES = frozenset({"short_factual_excerpt", "generated_social_summary", "summary_allowed"})


def clip_text(value: str, limit: int) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    if limit < 2:
        return "" if limit <= 0 else "…"
    prefix = value[:limit - 1]
    # Keep a whole word where possible. Ellipsis makes the shortening explicit.
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix.rstrip(" ,;:") + "…"


def prepare_summary(item: dict, limit: int = 360) -> str:
    """Select at most two sentences; never derive facts from a bare headline."""
    if item.get("content_policy") not in SUMMARY_POLICIES:
        return ""
    value = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()
    # Remove a Drupal author/timestamp header, only when its full signature matches.
    value = re.sub(r"^\S+\s+(?:dl|dt|dc|dj|dv|ds|dg)\.,\s+\d{1,2}/\d{1,2}/\d{4}\s+-\s+\d{1,2}:\d{2}\s+\d{1,2}-[A-Za-zÀ-ÿ]+-\d{4}\s+", "", value)
    if not value or value.casefold() == str(item.get("title") or "").strip().casefold():
        return ""
    if re.fullmatch(r"https?://\S+", value, flags=re.I):
        return ""
    # The break requires a capital letter; decimals and time notations stay intact.
    protected = re.sub(r"\b(?:Sr|Sra|Dr|Dra|núm|p\.ex)\.",
                       lambda match: match.group().replace(".", "\u2060"), value, flags=re.I)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý¿¡])", protected)
    selected = " ".join(sentences[:2]).replace("\u2060", ".")
    return clip_text(selected, limit)


def has_site_link(text: str) -> bool:
    for value in re.findall(r"https?://[^\s<>]+", text):
        try:
            url = urlsplit(value.rstrip(".,;!?)\"'"))
            if url.hostname == "soller-ara.github.io" and url.path.rstrip("/") == "/soller-ara":
                return True
        except ValueError:
            continue
    return False


def compose_instagram_caption(header: str, body: str, references: str, hashtags: str) -> str:
    """Budget optional prose while keeping source URLs and the home link intact."""
    header, body, references, hashtags = (str(value or "").strip()
                                          for value in (header, body, references, hashtags))
    # Test the retained references, not a body section which may be shortened.
    footer = "" if has_site_link("\n".join((header, references))) else SITE_LABEL
    tail = "\n\n".join(value for value in (references, footer, hashtags) if value)
    fixed = "\n\n".join(value for value in (header, tail) if value)
    if len(fixed) > INSTAGRAM_CAPTION_LIMIT and footer:
        # Branding is optional: it must never turn an otherwise valid send into an error.
        tail = "\n\n".join(value for value in (references, hashtags) if value)
        fixed = "\n\n".join(value for value in (header, tail) if value)
    if len(fixed) > INSTAGRAM_CAPTION_LIMIT:
        raise ValueError("Les referències obligatòries superen el límit de text d'Instagram; revisa els enllaços.")
    available = INSTAGRAM_CAPTION_LIMIT - len(fixed) - (2 if body and fixed else 0)
    body = clip_text(body, max(0, available))
    return "\n\n".join(value for value in (header, body, tail) if value)
