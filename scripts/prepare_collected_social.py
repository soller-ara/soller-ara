#!/usr/bin/env python3
"""Prepara una cua segura de publicacions recopilades per a Facebook/Instagram.

- No publica res per si mateix.
- Només selecciona contingut recent i no publicat abans.
- Respecta moderació, fonts desactivades, categories i configuració social.
- Per Instagram genera una targeta pròpia de Sóller Ara; no reutilitza imatges de tercers.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


try:
    from publication_state import alert_can_be_published, instagram_is_paused
except ModuleNotFoundError:
    from scripts.publication_state import alert_can_be_published, instagram_is_paused

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "social_distribution.json"
POSTS_FILE = ROOT / "data" / "posts.json"
LOG_FILE = ROOT / "data" / "social_publish_log.json"
QUEUE_FILE = ROOT / "data" / "social_auto_queue.json"
MODERATION_FILE = ROOT / "data" / "moderation.json"
SOURCES_FILE = ROOT / "sources.json"
CARD_DIR = ROOT / "assets" / "generated" / "social"
LOGO_FILE = ROOT / "assets" / "brand" / "logo-soller-ara-web.png"
IMAGE_BASE = "https://soller-ara.github.io/soller-ara/assets/generated/social"


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Format JSON no vàlid: {path.name}")
    for key in ("entries", "posts", "hidden_post_ids"):
        if key in payload and not isinstance(payload[key], list):
            raise ValueError(f"Format no vàlid: {path.name}/{key}")
    for key in ("entries", "posts"):
        if any(not isinstance(item, dict) for item in payload.get(key, [])):
            raise ValueError(f"Format no vàlid: {path.name}/{key}")
    if "entries" in fallback and "entries" not in payload:
        raise ValueError(f"Falta el registre d'entrades: {path.name}")
    return payload


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


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


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = str(text or "").split()
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


CATEGORY_CARD_STYLES = {
    "news": ("NOTÍCIES", "#2563eb"),
    "agenda": ("AGENDA", "#b45309"),
    "alerts": ("AVISOS", "#b42318"),
    "services": ("SERVEIS", "#0f766e"),
    "culture": ("CULTURA", "#7e22ce"),
    "sports": ("ESPORTS", "#15803d"),
    "commerce": ("COMERÇ", "#c2410c"),
    "politics": ("POLÍTICA", "#334155"),
    "social": ("XARXES", "#be185d"),
}


def draw_category_icon(draw: ImageDraw.ImageDraw, category: str, box: tuple[int, int, int, int], color: str) -> None:
    """Dibuixa una icona vectorial simple i estable, sense dependre de fonts emoji."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    line = max(7, int(w * 0.055))
    inset = int(w * 0.20)

    if category == "agenda":
        draw.rounded_rectangle((x0 + inset, y0 + inset, x1 - inset, y1 - inset), radius=12, outline=color, width=line)
        draw.line((x0 + inset, y0 + int(h * .38), x1 - inset, y0 + int(h * .38)), fill=color, width=line)
        draw.line((x0 + int(w * .37), y0 + int(h * .16), x0 + int(w * .37), y0 + int(h * .30)), fill=color, width=line)
        draw.line((x0 + int(w * .63), y0 + int(h * .16), x0 + int(w * .63), y0 + int(h * .30)), fill=color, width=line)
        for dx in (-0.16, 0.16):
            for dy in (0.05, 0.25):
                r = int(w * .035)
                px, py = int(cx + w * dx), int(cy + h * dy)
                draw.ellipse((px-r, py-r, px+r, py+r), fill=color)
        return

    if category == "alerts":
        pts = [(cx, y0 + int(h * .16)), (x1 - int(w * .16), y1 - int(h * .18)), (x0 + int(w * .16), y1 - int(h * .18)), (cx, y0 + int(h * .16))]
        draw.line(pts, fill=color, width=line)
        draw.line((cx, y0 + int(h * .39), cx, y0 + int(h * .61)), fill=color, width=line)
        r = int(w * .035)
        draw.ellipse((cx-r, y0 + int(h * .70)-r, cx+r, y0 + int(h * .70)+r), fill=color)
        return

    if category == "services":
        draw.line((x0 + int(w * .30), y1 - int(h * .28), x1 - int(w * .29), y0 + int(h * .29)), fill=color, width=line + 5)
        r = int(w * .13)
        draw.ellipse((x1 - int(w * .39)-r, y0 + int(h * .29)-r, x1 - int(w * .39)+r, y0 + int(h * .29)+r), outline=color, width=line)
        draw.ellipse((x0 + int(w * .30)-int(w*.07), y1 - int(h * .28)-int(w*.07), x0 + int(w * .30)+int(w*.07), y1 - int(h * .28)+int(w*.07)), outline=color, width=line)
        return

    if category == "culture":
        left = (x0 + int(w*.16), y0 + int(h*.23), x0 + int(w*.57), y1 - int(h*.20))
        right = (x0 + int(w*.43), y0 + int(h*.29), x1 - int(w*.14), y1 - int(h*.15))
        draw.rounded_rectangle(left, radius=22, outline=color, width=line)
        draw.rounded_rectangle(right, radius=22, outline=color, width=line)
        for bx in (left, right):
            lx0, ly0, lx1, ly1 = bx
            ey = ly0 + int((ly1-ly0)*.38)
            er = int(w*.025)
            draw.ellipse((lx0+int((lx1-lx0)*.30)-er, ey-er, lx0+int((lx1-lx0)*.30)+er, ey+er), fill=color)
            draw.ellipse((lx0+int((lx1-lx0)*.70)-er, ey-er, lx0+int((lx1-lx0)*.70)+er, ey+er), fill=color)
            draw.arc((lx0+int((lx1-lx0)*.24), ly0+int((ly1-ly0)*.46), lx0+int((lx1-lx0)*.76), ly0+int((ly1-ly0)*.78)), 10, 170, fill=color, width=max(4,line//2))
        return

    if category == "sports":
        r = int(w * .22)
        draw.ellipse((cx-r, cy-r+int(h*.08), cx+r, cy+r+int(h*.08)), outline=color, width=line)
        draw.polygon([(cx-int(w*.16), y0+int(h*.18)), (cx-int(w*.03), cy-int(h*.08)), (cx-int(w*.24), cy-int(h*.02))], fill=color)
        draw.polygon([(cx+int(w*.16), y0+int(h*.18)), (cx+int(w*.03), cy-int(h*.08)), (cx+int(w*.24), cy-int(h*.02))], fill=color)
        star = [(cx, cy-int(h*.06)), (cx+int(w*.04), cy+int(h*.03)), (cx+int(w*.14), cy+int(h*.03)),
                (cx+int(w*.06), cy+int(h*.09)), (cx+int(w*.09), cy+int(h*.19)), (cx, cy+int(h*.13)),
                (cx-int(w*.09), cy+int(h*.19)), (cx-int(w*.06), cy+int(h*.09)), (cx-int(w*.14), cy+int(h*.03)),
                (cx-int(w*.04), cy+int(h*.03))]
        draw.polygon(star, fill=color)
        return

    if category == "commerce":
        draw.rectangle((x0+int(w*.20), y0+int(h*.39), x1-int(w*.20), y1-int(h*.18)), outline=color, width=line)
        draw.line((x0+int(w*.16), y0+int(h*.39), x1-int(w*.16), y0+int(h*.39)), fill=color, width=line)
        for i in range(4):
            sx0 = x0 + int(w*(.18 + i*.16))
            draw.polygon([(sx0, y0+int(h*.22)), (sx0+int(w*.12), y0+int(h*.22)), (sx0+int(w*.10), y0+int(h*.39)), (sx0+int(w*.02), y0+int(h*.39))], outline=color)
        draw.rectangle((cx-int(w*.07), y0+int(h*.58), cx+int(w*.07), y1-int(h*.18)), outline=color, width=max(4,line//2))
        return

    if category == "politics":
        draw.polygon([(cx, y0+int(h*.18)), (x1-int(w*.17), y0+int(h*.38)), (x0+int(w*.17), y0+int(h*.38))], outline=color)
        draw.line((x0+int(w*.20), y0+int(h*.42), x1-int(w*.20), y0+int(h*.42)), fill=color, width=line)
        for px in (0.31, 0.43, 0.57, 0.69):
            xx = x0 + int(w*px)
            draw.line((xx, y0+int(h*.45), xx, y1-int(h*.23)), fill=color, width=line)
        draw.line((x0+int(w*.17), y1-int(h*.20), x1-int(w*.17), y1-int(h*.20)), fill=color, width=line)
        draw.line((x0+int(w*.13), y1-int(h*.14), x1-int(w*.13), y1-int(h*.14)), fill=color, width=line)
        return

    if category == "social":
        phone = (x0+int(w*.29), y0+int(h*.15), x1-int(w*.29), y1-int(h*.15))
        draw.rounded_rectangle(phone, radius=20, outline=color, width=line)
        draw.line((x0+int(w*.40), y0+int(h*.25), x1-int(w*.40), y0+int(h*.25)), fill=color, width=max(4,line//2))
        rr = int(w*.025)
        draw.ellipse((cx-rr, y1-int(h*.24)-rr, cx+rr, y1-int(h*.24)+rr), fill=color)
        draw.rounded_rectangle((x0+int(w*.13), y0+int(h*.38), x0+int(w*.47), y0+int(h*.59)), radius=14, outline=color, width=max(4,line//2))
        draw.polygon([(x0+int(w*.24), y0+int(h*.59)), (x0+int(w*.20), y0+int(h*.68)), (x0+int(w*.32), y0+int(h*.59))], fill=color)
        return

    # Notícies: diari; també és el fallback.
    draw.rounded_rectangle((x0 + int(w*.17), y0 + int(h*.20), x1 - int(w*.17), y1 - int(h*.20)), radius=10, outline=color, width=line)
    draw.rectangle((x0+int(w*.26), y0+int(h*.32), x0+int(w*.47), y0+int(h*.51)), outline=color, width=max(4,line//2))
    for yy in (0.33, 0.43, 0.54, 0.64):
        draw.line((x0+int(w*.54), y0+int(h*yy), x1-int(w*.26), y0+int(h*yy)), fill=color, width=max(4,line//2))
    draw.line((x0+int(w*.26), y0+int(h*.62), x0+int(w*.47), y0+int(h*.62)), fill=color, width=max(4,line//2))
    draw.line((x0+int(w*.26), y0+int(h*.72), x1-int(w*.26), y0+int(h*.72)), fill=color, width=max(4,line//2))


def generate_card(post: dict) -> str:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    post_id = str(post.get("id") or "")
    path = CARD_DIR / f"{post_id}.jpg"

    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#f6f7f5")
    draw = ImageDraw.Draw(image)

    primary = "#0f766e"
    text_color = "#1e2927"
    muted = "#64716f"
    surface = "#ffffff"
    category = str(post.get("category") or "news")
    category_label, accent = CATEGORY_CARD_STYLES.get(category, CATEGORY_CARD_STYLES["news"])

    draw.rounded_rectangle((70, 70, width - 70, height - 70), radius=52, fill=surface)

    if LOGO_FILE.exists():
        with Image.open(LOGO_FILE) as source_logo:
            logo = source_logo.convert("RGBA").resize((160, 160), Image.Resampling.LANCZOS)
            image.paste(logo, (110, 110), logo)
    else:
        draw.rounded_rectangle((110, 110, 270, 270), radius=42, fill=primary)
        draw.text((142, 148), "SA", font=load_font(68, bold=True), fill="#ffffff")

    brand_font = load_font(38, bold=True)
    title_font = load_font(72, bold=True)
    source_font = load_font(34, bold=True)
    footer_font = load_font(30, bold=False)

    draw.text((310, 140), "SÓLLER ARA", font=brand_font, fill=primary)
    draw.text((310, 200), category_label, font=footer_font, fill=accent)
    draw.rounded_rectangle((790, 105, 970, 285), radius=42, fill=accent)
    draw_category_icon(draw, category, (790, 105, 970, 285), "#ffffff")

    lines = wrap(draw, str(post.get("title") or ""), title_font, width - 220)
    if len(lines) > 7:
        lines = lines[:7]
        lines[-1] = lines[-1].rstrip(" .,:;") + "…"

    y = 390
    for line in lines:
        draw.text((110, y), line, font=title_font, fill=text_color)
        box = draw.textbbox((0, 0), line, font=title_font)
        y += (box[3] - box[1]) + 24

    draw.line((110, height - 310, width - 110, height - 310), fill=accent, width=5)
    draw.text((110, height - 255), f"Font: {post.get('source') or 'Font original'}", font=source_font, fill=text_color)
    draw.text((110, height - 205), "Informació recopilada per Sóller Ara", font=footer_font, fill=muted)

    image.save(path, "JPEG", quality=92, optimize=True)
    return f"{IMAGE_BASE}/{post_id}.jpg"

def success_pairs(log: dict) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for entry in log.get("entries") or []:
        if entry.get("status") == "success" and entry.get("post_id") and entry.get("platform"):
            pairs.add((str(entry["post_id"]), str(entry["platform"])))
    return pairs


def save_queue(payload: dict) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    config = load_json(CONFIG_FILE, {"enabled": False})
    if not config.get("enabled"):
        save_queue({"version": 1, "enabled": False, "entries": []})
        print("SOCIAL_AUTO: desactivat; cua buida.")
        return 0

    posts_payload = load_json(POSTS_FILE, {"posts": []})
    log = load_json(LOG_FILE, {"entries": []})
    moderation = load_json(MODERATION_FILE, {"hidden_post_ids": []})
    source_payload = load_json(SOURCES_FILE, {"sources": []})

    hidden = set(moderation.get("hidden_post_ids") or [])
    active_sources = {
        str(item.get("id"))
        for item in (source_payload.get("sources") or [])
        if item.get("id") and item.get("enabled", True) is not False
    }
    published = success_pairs(log)

    global_platforms = config.get("platforms") or {}
    categories = config.get("categories") or {}
    source_rules = config.get("sources") or {}
    max_age = int(config.get("max_age_hours", 6) or 6)
    max_posts = max(1, int(config.get("max_posts_per_run", 3) or 3))
    one_per_source = bool(config.get("one_post_per_source_per_run", True))
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=max_age)

    candidates: list[dict] = []
    for post in posts_payload.get("posts") or []:
        post_id = str(post.get("id") or "")
        source_id = str(post.get("source_id") or "")
        category = str(post.get("category") or "news")
        if not post_id or post.get("source_type") == "own" or not alert_can_be_published(post, now):
            continue
        if post_id in hidden or source_id not in active_sources:
            continue
        if categories.get(category, True) is False:
            continue

        published_at = parse_date(post.get("published_at"))
        if published_at is None or not threshold <= published_at <= now:
            continue

        rules = source_rules.get(source_id)
        if not isinstance(rules, dict):
            continue

        platforms: list[str] = []
        for platform in ("facebook", "instagram"):
            if platform == "instagram" and instagram_is_paused(log, now):
                continue
            if global_platforms.get(platform, False) and rules.get(platform, False):
                if (post_id, platform) not in published:
                    platforms.append(platform)
        if not platforms:
            continue

        item = dict(post)
        item["_published_at"] = published_at
        item["_platforms"] = platforms
        candidates.append(item)

    candidates.sort(key=lambda x: x["_published_at"], reverse=True)

    selected: list[dict] = []
    used_sources: set[str] = set()
    for post in candidates:
        source_id = str(post.get("source_id") or "")
        if one_per_source and source_id in used_sources:
            continue
        used_sources.add(source_id)
        selected.append(post)
        if len(selected) >= max_posts:
            break

    queue_entries: list[dict] = []
    for post in selected:
        platforms = list(post.pop("_platforms"))
        post.pop("_published_at", None)
        image_url = generate_card(post) if "instagram" in platforms else ""
        queue_entries.append({
            "post_id": post.get("id"),
            "title": post.get("title"),
            "summary": post.get("summary") or "",
            "source": post.get("source"),
            "source_id": post.get("source_id"),
            "source_type": post.get("source_type"),
            "category": post.get("category"),
            "language": post.get("language"),
            "published_at": post.get("published_at"),
            **{key: post[key] for key in ("alert_status", "alert_valid_from", "alert_valid_until") if key in post},
            "original_url": post.get("url"),
            "content_policy": post.get("content_policy"),
            "rights_status": post.get("rights_status"),
            "platforms": platforms,
            "image_url": image_url,
        })

    payload = {
        "version": 1,
        "enabled": True,
        "generated_at": datetime.now(timezone.utc).isoformat() if queue_entries else None,
        "entries": queue_entries,
    }
    save_queue(payload)
    print(f"SOCIAL_AUTO: {len(queue_entries)} publicacions preparades.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
