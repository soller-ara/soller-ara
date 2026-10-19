#!/usr/bin/env python3
"""Prepare search metadata in the deployment copy, without changing publication data.

Run AFTER content has been committed and BEFORE uploading the Pages artifact.
Requires no network, credentials, Pillow or third-party packages.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://soller-ara.github.io/soller-ara"
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
STATIC = ("index.html", "enllacos.html", "transparency.html", "privacy.html", "data-deletion.html")
BLOCK = re.compile(r'\s*<!-- SEO:START -->.*?<!-- SEO:END -->', re.S)
ARCHIVE = re.compile(r'\s*<!-- SEO:LINKS:START -->.*?<!-- SEO:LINKS:END -->', re.S)


def text(value: object) -> str:
    return " ".join(str(value or "").split())


def useful(post: dict) -> bool:
    """Conservative project rule, NOT a Google minimum word/character count."""
    title = text(post.get("title"))
    body = re.sub(r'https?://\S+', '', text(post.get("summary")))
    return (len(title) >= 10 and title.casefold() not in
            {"publicació de xarxa", "publicacion de red", "publicación de red", "sóller ara"}
            and len(body.strip()) >= 80 and body.strip().casefold() != title.casefold())


def valid_date(value: str) -> str | None:
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.isoformat() if date.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def last_change(root: Path, relative: str) -> str | None:
    # A shallow checkout cannot establish the last change of an old file.
    # Omit the optional date instead of inventing one from checkout time.
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                                 cwd=root, capture_output=True, text=True, check=True)
        if shallow.stdout.strip() != "false":
            return None
        result = subprocess.run(["git", "log", "-1", "--format=%cI", "--", relative],
                                cwd=root, capture_output=True, text=True, check=True)
        return valid_date(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class Tag(HTMLParser):
    def handle_starttag(self, name, attrs):
        self.attrs = dict(attrs)


def replace_metadata(document: str, markup: str, *, detail: bool) -> str:
    if len(re.findall(r'</head\s*>', document, re.I)) != 1:
        raise ValueError("Expected one HTML head")
    head, tail = re.split(r'</head\s*>', document, maxsplit=1, flags=re.I)
    head = BLOCK.sub('', head)

    def keep(match):
        parser = Tag()
        parser.feed(match.group())
        attrs = {k.lower(): str(v or '').lower() for k, v in parser.attrs.items()}
        if attrs.get('rel') == 'canonical' or attrs.get('name') == 'robots':
            return ''
        if detail and (attrs.get('name') in {'description', 'twitter:description'} or
                       attrs.get('property') in {'og:description', 'article:published_time', 'article:modified_time'}):
            return ''
        return match.group()

    head = re.sub(r'<(?:meta|link)\b[^>]*>', keep, head, flags=re.I)
    return head.rstrip() + '\n  <!-- SEO:START -->\n' + markup + '\n  <!-- SEO:END -->\n</head>' + tail


def build(root: Path = ROOT) -> dict:
    manual = json.loads((root / 'data/manual_posts.json').read_text(encoding='utf-8'))
    moderation = json.loads((root / 'data/moderation.json').read_text(encoding='utf-8'))
    posts = manual['posts']
    hidden = moderation['hidden_post_ids']
    if not isinstance(posts, list) or any(not isinstance(p, dict) for p in posts) or not isinstance(hidden, list):
        raise ValueError('Invalid publication inventory')
    by_id = {}
    for post in posts:
        identifier = str(post.get('id') or '')
        if not re.fullmatch(r'soller-ara-[0-9a-f]{16}', identifier) or identifier in by_id:
            raise ValueError('Invalid or duplicate local publication ID')
        by_id[identifier] = post

    entries = []
    writes = {}
    for relative in STATIC:
        path = root / relative
        document = path.read_text(encoding='utf-8')
        url = SITE + ('/' if relative == 'index.html' else '/' + relative)
        writes[path] = replace_metadata(document,
            f'  <link rel="canonical" href="{url}" />\n  <meta name="robots" content="index,follow,max-image-preview:large" />', detail=False)
        # Dynamic feeds change independently of their HTML. Do not date them
        # with the latest poll, deployment or an unrelated source publication.
        modified = None if relative in {'index.html', 'enllacos.html'} else last_change(root, relative)
        entries.append((url, modified))

    included = []
    excluded = 0
    for path in sorted((root / 'noticies').glob('*.html')):
        post = by_id.get(path.stem)
        indexable = bool(post and post.get('source_type') == 'own' and path.stem not in hidden and useful(post))
        url = f'{SITE}/noticies/{path.name}'
        robots = 'index,follow,max-image-preview:large' if indexable else 'noindex,follow'
        markup = f'  <link rel="canonical" href="{url}" />\n  <meta name="robots" content="{robots}" />'
        if post:
            description = html.escape(text(post.get('summary'))[:280], quote=True)
            markup += (f'\n  <meta name="description" content="{description}" />'
                       f'\n  <meta property="og:description" content="{description}" />'
                       f'\n  <meta name="twitter:description" content="{description}" />')
        if indexable:
            modified = last_change(root, str(path.relative_to(root)))
            entries.append((url, modified))
            included.append((post, url))
            # A reference page is a WebPage, not an article authored by us.
            schema = {'@context': 'https://schema.org', '@type': 'WebPage',
                      'url': url, 'name': text(post.get('title')),
                      'description': text(post.get('summary'))[:280],
                      'inLanguage': post.get('language') or 'ca',
                      'isPartOf': {'@type': 'WebSite', 'name': 'Sóller Ara', 'url': SITE + '/'}}
            published = valid_date(str(post.get('published_at') or ''))
            if published:
                schema['datePublished'] = published
            if modified:
                schema['dateModified'] = modified
            encoded = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            markup += f'\n  <script type="application/ld+json">{encoded}</script>'
        else:
            excluded += 1
        writes[path] = replace_metadata(path.read_text(encoding='utf-8'), markup, detail=True)

    # Crawlable links remain available without executing the existing JS feed.
    # This archive uses the persistent inventory, including posts outside Ara.
    archive_path = root / 'enllacos.html'
    archive = ARCHIVE.sub('', writes[archive_path])
    links = '\n'.join(f'          <li><a href="{url}">{html.escape(text(post.get("title")))}</a></li>'
                      for post, url in sorted(included, key=lambda item: str(item[0].get('published_at') or ''), reverse=True))
    section = ('\n      <!-- SEO:LINKS:START -->\n      <details>\n'
               '        <summary>Publicacions amb resum</summary>\n        <ul>\n' + links +
               '\n        </ul>\n      </details>\n      <!-- SEO:LINKS:END -->\n    ')
    writes[archive_path] = re.sub(r'\s*</section>', lambda _: section + '</section>', archive, count=1)

    ET.register_namespace('', NS)
    sitemap = ET.Element(f'{{{NS}}}urlset')
    for url, modified in entries:
        entry = ET.SubElement(sitemap, f'{{{NS}}}url')
        ET.SubElement(entry, f'{{{NS}}}loc').text = url
        if modified:
            ET.SubElement(entry, f'{{{NS}}}lastmod').text = modified
    ET.indent(sitemap, space='  ')
    writes[root / 'sitemap.xml'] = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(sitemap, encoding='unicode') + '\n'
    # Validate everything before touching deployment files. No JSON writes.
    for path, content in writes.items():
        path.write_text(content, encoding='utf-8')
    return {'static': len(STATIC), 'publications': len(included), 'noindex': excluded, 'urls': len(entries)}


if __name__ == '__main__':
    print('SEO_BUILD ' + json.dumps(build(), sort_keys=True))
