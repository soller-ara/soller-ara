#!/usr/bin/env python3
"""Afegeix una publicació pròpia de Sóller Ara al feed.

No conté credencials socials. Manté data/manual_posts.json com a font persistent
i actualitza data/posts.json + data/posts.js perquè la publicació aparegui
immediatament sense esperar la següent recopilació horària.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MANUAL_FILE = ROOT / "data" / "manual_posts.json"
POSTS_FILE = ROOT / "data" / "posts.json"
POSTS_JS_FILE = ROOT / "data" / "posts.js"
DETAIL_DIR = ROOT / "noticies"
GENERATED_DIR = ROOT / "assets" / "generated"
SITE_URL = "https://soller-ara.github.io/soller-ara"

TITLE = os.environ.get("POST_TITLE", "").strip()
BODY = os.environ.get("POST_BODY", "").strip()
CATEGORY = os.environ.get("POST_CATEGORY", "news").strip() or "news"
LANGUAGE = os.environ.get("POST_LANGUAGE", "ca").strip() or "ca"
IMAGE_URL = os.environ.get("POST_IMAGE_URL", "").strip()
SOURCE_NAME = os.environ.get("POST_SOURCE_NAME", "").strip()
ORIGINAL_URL = os.environ.get("POST_ORIGINAL_URL", "").strip()
CONFIRMATION = os.environ.get("PUBLISH_CONFIRMATION", "").strip()
PUBLISH_KEY = (os.environ.get("PUBLISH_KEY", "").strip() or os.environ.get("GITHUB_RUN_ID", "").strip())

ALLOWED_CATEGORIES = {
    "news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics", "social"
}


def stable_id(title: str, published_at: str) -> str:
    raw = f"{published_at}|{title}".encode("utf-8")
    return "soller-ara-" + hashlib.sha1(raw).hexdigest()[:16]


def stable_id_from_key(key: str) -> str:
    raw = f"publish-key|{key}".encode("utf-8")
    return "soller-ara-" + hashlib.sha1(raw).hexdigest()[:16]


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_social_card(post_id: str, title: str, category: str) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#f6f7f5")
    draw = ImageDraw.Draw(image)

    primary = "#0f766e"
    text_color = "#1e2927"
    muted = "#64716f"
    surface = "#ffffff"

    draw.rounded_rectangle((70, 70, width - 70, height - 70), radius=52, fill=surface)
    draw.rounded_rectangle((110, 110, 270, 270), radius=42, fill=primary)

    brand_font = load_font(68, bold=True)
    category_font = load_font(38, bold=True)
    title_font = load_font(72, bold=True)
    footer_font = load_font(34, bold=False)

    draw.text((142, 148), "SA", font=brand_font, fill="#ffffff")
    draw.text((310, 140), "SÓLLER ARA", font=category_font, fill=primary)
    draw.text((310, 200), category.upper(), font=footer_font, fill=muted)

    lines = wrap_text(draw, title, title_font, width - 220)
    max_lines = 7
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,:;") + "…"

    y = 390
    line_gap = 24
    for line in lines:
        draw.text((110, y), line, font=title_font, fill=text_color)
        box = draw.textbbox((0, 0), line, font=title_font)
        y += (box[3] - box[1]) + line_gap

    draw.line((110, height - 240, width - 110, height - 240), fill="#dde5e2", width=3)
    draw.text((110, height - 190), "soller-ara · Informació local", font=footer_font, fill=muted)

    path = GENERATED_DIR / f"{post_id}.jpg"
    image.save(path, "JPEG", quality=92, optimize=True)
    return f"{SITE_URL}/assets/generated/{post_id}.jpg"


def main() -> int:
    if CONFIRMATION != "PUBLICAR":
        print("ERROR: cal escriure PUBLICAR per confirmar.", file=sys.stderr)
        return 2
    if not TITLE:
        print("ERROR: falta el títol.", file=sys.stderr)
        return 2
    if not BODY:
        print("ERROR: falta el text de la publicació.", file=sys.stderr)
        return 2
    if CATEGORY not in ALLOWED_CATEGORIES:
        print(f"ERROR: categoria no vàlida: {CATEGORY}", file=sys.stderr)
        return 2
    if bool(SOURCE_NAME) != bool(ORIGINAL_URL):
        print("ERROR: font i enllaç original s'han d'indicar junts.", file=sys.stderr)
        return 2
    if ORIGINAL_URL:
        parsed_original = urlparse(ORIGINAL_URL)
        if parsed_original.scheme != "https" or not parsed_original.netloc:
            print("ERROR: l'enllaç original ha de ser https.", file=sys.stderr)
            return 2
    if len(SOURCE_NAME) > 120:
        print("ERROR: el nom de la font és massa llarg.", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc).isoformat()
    post_id = stable_id_from_key(PUBLISH_KEY) if PUBLISH_KEY else stable_id(TITLE, now)

    post_url = f"{SITE_URL}/noticies/{post_id}.html"
    final_image_url = IMAGE_URL or generate_social_card(post_id, TITLE, CATEGORY)

    display_source = SOURCE_NAME or "Sóller Ara"
    source_id = "soller-ara" if not SOURCE_NAME else "manual-" + hashlib.sha1(SOURCE_NAME.casefold().encode("utf-8")).hexdigest()[:12]
    post = {
        "id": post_id,
        "category": CATEGORY,
        "source_id": source_id,
        "source": display_source,
        "source_type": "own",
        "language": LANGUAGE,
        "locality": "Sóller",
        "published_at": now,
        "title": TITLE,
        "summary": BODY,
        "url": post_url,
        "content_policy": "manual_link_reference" if ORIGINAL_URL else "owned_content",
        "rights_status": "no_reuse_reference_only" if ORIGINAL_URL else "owned",
        "image_allowed": bool(final_image_url),
    }
    if ORIGINAL_URL:
        post["original_url"] = ORIGINAL_URL
    if final_image_url:
        post["media_url"] = final_image_url
        post["media_type"] = "image"

    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = html.escape(TITLE, quote=True)
    safe_body = html.escape(BODY, quote=True)
    body_html = "<br />".join(safe_body.splitlines())
    safe_url = html.escape(post_url, quote=True)
    safe_image = html.escape(final_image_url, quote=True) if final_image_url else ""
    safe_source = html.escape(display_source, quote=True)
    safe_original = html.escape(ORIGINAL_URL, quote=True) if ORIGINAL_URL else ""
    reference_html = (
        f'<p class="article-source">Font original: <strong>{safe_source}</strong> · <a class="origin-link" href="{safe_original}" target="_blank" rel="noopener noreferrer">Veure publicació original →</a></p>'
        if safe_original else ""
    )
    image_meta = (
        f'<meta property="og:image" content="{safe_image}" />\n'
        f'  <meta name="twitter:image" content="{safe_image}" />'
        if safe_image else ""
    )
    image_html = (
        f'<img class="article-image" src="{safe_image}" alt="" />'
        if safe_image else ""
    )
    detail_html = f"""<!doctype html>
<html lang="{html.escape(LANGUAGE, quote=True)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#0f766e" />
  <title>{safe_title} · Sóller Ara</title>
  <meta name="description" content="{safe_body[:280]}" />
  <link rel="canonical" href="{safe_url}" />
  <link rel="stylesheet" href="../styles.css?v=0.38" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="Sóller Ara" />
  <meta property="og:title" content="{safe_title}" />
  <meta property="og:description" content="{safe_body[:280]}" />
  <meta property="og:url" content="{safe_url}" />
  {image_meta}
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{safe_title}" />
  <meta name="twitter:description" content="{safe_body[:280]}" />
</head>
<body>
  <header class="topbar">
    <a class="brand-wrap" href="../index.html" style="text-decoration:none">
      <div class="brand-mark" aria-hidden="true">SA</div>
      <div><h1>Sóller Ara</h1><p>Tot el que passa a Sóller, en un sol lloc.</p></div>
    </a>
  </header>
  <main class="legal-page">
    <a class="legal-back" href="../index.html">← Tornar a Sóller Ara</a>
    <article class="legal-card own-article">
      <p class="eyebrow">{safe_source}</p>
      <h1>{safe_title}</h1>
      <p class="article-date">{now}</p>
      {image_html}
      <div class="article-body"><p>{body_html}</p></div>
      {reference_html}
      <p><a class="origin-link" href="../index.html">Veure més informació a Sóller Ara →</a></p>
    </article>
  </main>
  <footer class="footer"><p>© 2026 Sóller Ara · Projecte sense ànim de lucre</p></footer>
  <script src="../analytics.js?v=1" defer></script>
</body>
</html>
"""
    detail_path = DETAIL_DIR / f"{post_id}.html"
    detail_path.write_text(detail_html, encoding="utf-8")

    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as env_file:
            env_file.write(f"OWN_POST_ID={post_id}\n")
            env_file.write(f"OWN_POST_URL={post_url}\n")
            env_file.write(f"OWN_IMAGE_URL={final_image_url}\n")

    if MANUAL_FILE.exists():
        manual = json.loads(MANUAL_FILE.read_text(encoding="utf-8"))
    else:
        manual = {"version": 1, "posts": []}

    manual_posts = manual.get("posts") or []
    manual_posts = [item for item in manual_posts if item.get("id") != post_id]
    manual_posts.append(post)
    manual["posts"] = manual_posts
    MANUAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_FILE.write_text(json.dumps(manual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Actualització immediata del feed generat existent.
    if POSTS_FILE.exists():
        payload = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    else:
        payload = {
            "version": 38,
            "generator_version": "0.38",
            "fetched_at": now,
            "source_count": 0,
            "source_status": [],
            "social_integration_status": [],
            "post_count": 0,
            "related_pair_count": 0,
            "errors": [],
            "posts": [],
        }

    generated_posts = payload.get("posts") or []
    generated_posts = [item for item in generated_posts if item.get("id") != post_id]
    generated_posts.insert(0, post)
    payload["posts"] = generated_posts
    payload["post_count"] = len(generated_posts)
    payload["fetched_at"] = now

    json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    POSTS_FILE.write_text(json_payload + "\n", encoding="utf-8")
    POSTS_JS_FILE.write_text("window.SOLLER_ARA_DATA = " + json_payload + ";\n", encoding="utf-8")

    print(f"RESULTAT: publicació pròpia creada amb id={post_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
