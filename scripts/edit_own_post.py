#!/usr/bin/env python3
"""Edita una publicació pròpia de Sóller Ara sense crear-ne una de nova."""

from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MANUAL_FILE = ROOT / "data" / "manual_posts.json"
POSTS_FILE = ROOT / "data" / "posts.json"
POSTS_JS_FILE = ROOT / "data" / "posts.js"
DETAIL_DIR = ROOT / "noticies"
GENERATED_DIR = ROOT / "assets" / "generated"
LOGO_FILE = ROOT / "assets" / "brand" / "logo-soller-ara-web.png"
SITE_URL = "https://soller-ara.github.io/soller-ara"

POST_ID = os.environ.get("POST_ID", "").strip()
TITLE = os.environ.get("POST_TITLE", "").strip()
BODY = os.environ.get("POST_BODY", "").strip()
CATEGORY = os.environ.get("POST_CATEGORY", "news").strip() or "news"
LANGUAGE = os.environ.get("POST_LANGUAGE", "ca").strip() or "ca"
IMAGE_URL = os.environ.get("POST_IMAGE_URL", "").strip()
CONFIRMATION = os.environ.get("EDIT_CONFIRMATION", "").strip()

ALLOWED_CATEGORIES = {
    "news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics"
}
ALLOWED_LANGUAGES = {"ca", "es", "en"}


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


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
    if LOGO_FILE.exists():
        with Image.open(LOGO_FILE) as source_logo:
            logo = source_logo.convert("RGB").resize((160, 160), Image.Resampling.LANCZOS)
            image.paste(logo, (110, 110))
    else:
        draw.rounded_rectangle((110, 110, 270, 270), radius=42, fill=primary)
        draw.text((142, 148), "SA", font=load_font(68, bold=True), fill="#ffffff")

    category_font = load_font(38, bold=True)
    title_font = load_font(72, bold=True)
    footer_font = load_font(34, bold=False)

    draw.text((310, 140), "SÓLLER ARA", font=category_font, fill=primary)
    draw.text((310, 200), category.upper(), font=footer_font, fill=muted)

    lines = wrap_text(draw, title, title_font, width - 220)
    if len(lines) > 7:
        lines = lines[:7]
        lines[-1] = lines[-1].rstrip(" .,:;") + "…"

    y = 390
    for line in lines:
        draw.text((110, y), line, font=title_font, fill=text_color)
        box = draw.textbbox((0, 0), line, font=title_font)
        y += (box[3] - box[1]) + 24

    draw.line((110, height - 240, width - 110, height - 240), fill="#dde5e2", width=3)
    draw.text((110, height - 190), "soller-ara · Informació local", font=footer_font, fill=muted)

    path = GENERATED_DIR / f"{post_id}.jpg"
    image.save(path, "JPEG", quality=92, optimize=True)
    return f"{SITE_URL}/assets/generated/{post_id}.jpg"


def is_generated_image(post_id: str, media_url: str) -> bool:
    if not media_url:
        return False
    return Path(urlparse(media_url).path).name == f"{post_id}.jpg" and "/assets/generated/" in media_url


def render_detail(post: dict) -> None:
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)

    post_id = post["id"]
    title = str(post.get("title") or "")
    body = str(post.get("summary") or "")
    language = str(post.get("language") or "ca")
    published_at = str(post.get("published_at") or "")
    post_url = str(post.get("url") or f"{SITE_URL}/noticies/{post_id}.html")
    image_url = str(post.get("media_url") or "")
    source_name = str(post.get("source") or "Sóller Ara")
    original_url = str(post.get("original_url") or "")

    safe_title = html.escape(title, quote=True)
    safe_body = html.escape(body, quote=True)
    body_html = "<br />".join(safe_body.splitlines())
    safe_url = html.escape(post_url, quote=True)
    safe_image = html.escape(image_url, quote=True) if image_url else ""
    safe_source = html.escape(source_name, quote=True)
    safe_original = html.escape(original_url, quote=True) if original_url else ""
    reference_html = (
        f'<p class="article-source">Font original: <strong>{safe_source}</strong> · <a class="origin-link" href="{safe_original}" target="_blank" rel="noopener noreferrer">Veure publicació original →</a></p>'
        if safe_original else ""
    )
    image_meta = (
        f'<meta property="og:image" content="{safe_image}" />\n'
        f'  <meta name="twitter:image" content="{safe_image}" />'
        if safe_image else ""
    )
    image_html = f'<img class="article-image" src="{safe_image}" alt="" />' if safe_image else ""

    detail_html = f"""<!doctype html>
<html lang="{html.escape(language, quote=True)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#0f766e" />
  <title>{safe_title} · Sóller Ara</title>
  <meta name="description" content="{safe_body[:280]}" />
  <link rel="canonical" href="{safe_url}" />
  <link rel="icon" href="../favicon.ico" sizes="any" />
  <link rel="icon" type="image/png" sizes="48x48" href="../assets/brand/favicon-48.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="../assets/brand/apple-touch-icon.png" />
  <link rel="stylesheet" href="../styles.css?v=0.64" />
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
      <div class="brand-mark"><img src="../assets/brand/logo-soller-ara-web.png" width="48" height="48" alt="" /></div>
      <div><h1>Sóller Ara</h1><p>Tot el que passa a Sóller, en un sol lloc.</p></div>
    </a>
  </header>
  <main class="legal-page">
    <a class="legal-back" href="../index.html">← Tornar a Sóller Ara</a>
    <article class="legal-card own-article">
      <p class="eyebrow">{safe_source}</p>
      <h1>{safe_title}</h1>
      <p class="article-date">{html.escape(published_at)}</p>
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
    (DETAIL_DIR / f"{post_id}.html").write_text(detail_html, encoding="utf-8")


def main() -> int:
    if CONFIRMATION != "GUARDAR":
        print("ERROR: cal escriure GUARDAR per confirmar.", file=sys.stderr)
        return 2
    if not POST_ID or not TITLE or not BODY:
        print("ERROR: falten dades obligatòries.", file=sys.stderr)
        return 2
    if CATEGORY not in ALLOWED_CATEGORIES or LANGUAGE not in ALLOWED_LANGUAGES:
        print("ERROR: categoria o idioma no vàlid.", file=sys.stderr)
        return 2

    manual = load_json(MANUAL_FILE, {"version": 1, "posts": []})
    manual_posts = manual.get("posts") or []
    target = next((item for item in manual_posts if item.get("id") == POST_ID), None)
    if target is None or target.get("source_type") != "own":
        print("ERROR: no s'ha trobat aquesta publicació pròpia.", file=sys.stderr)
        return 1

    old_media = str(target.get("media_url") or "")
    if IMAGE_URL:
        final_image = IMAGE_URL
    elif is_generated_image(POST_ID, old_media):
        final_image = generate_social_card(POST_ID, TITLE, CATEGORY)
    else:
        final_image = old_media

    updated = dict(target)
    updated.update({
        "category": CATEGORY,
        "language": LANGUAGE,
        "title": TITLE,
        "summary": BODY,
        "rights_status": "no_reuse_reference_only" if target.get("original_url") else "owned",
        "content_policy": "manual_link_reference" if target.get("original_url") else "owned_content",
        "image_allowed": bool(final_image),
    })

    if final_image:
        updated["media_url"] = final_image
        updated["media_type"] = "image"
    else:
        updated.pop("media_url", None)
        updated.pop("media_type", None)

    manual["posts"] = [updated if item.get("id") == POST_ID else item for item in manual_posts]
    MANUAL_FILE.write_text(json.dumps(manual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    payload = load_json(POSTS_FILE, {"posts": []})
    posts = payload.get("posts") or []
    payload["posts"] = [updated if item.get("id") == POST_ID else item for item in posts]
    payload["post_count"] = len(payload["posts"])

    json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    POSTS_FILE.write_text(json_payload + "\n", encoding="utf-8")
    POSTS_JS_FILE.write_text("window.SOLLER_ARA_DATA = " + json_payload + ";\n", encoding="utf-8")

    render_detail(updated)
    print(f"RESULTAT: publicació pròpia editada: {POST_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
