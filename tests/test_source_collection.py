import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_sources", ROOT / "scripts/update_sources.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class SourceCollectionTests(unittest.TestCase):
    def test_clear_title_category_prevents_summary_misclassification(self):
        self.assertEqual(collector.categorize("Tall de trànsit al carrer de la Lluna", "Cursa i concert"), "alerts")
        self.assertEqual(collector.categorize("Ofertes de feina a Sóller", "Agenda cultural i esportiva"), "services")
        self.assertEqual(collector.categorize("El regidor explica la moció presentada", "Jornada i concert"), "politics")
        self.assertEqual(collector.categorize("Torneig de bàsquet a Son Angelats", "Exposició i tallers"), "sports")

    def test_category_override_accepts_politics_and_social(self):
        old_file = collector.MODERATION_FILE
        with tempfile.TemporaryDirectory() as temp:
            collector.MODERATION_FILE = Path(temp) / "moderation.json"
            collector.MODERATION_FILE.write_text(json.dumps({"category_overrides": {"p": "politics", "s": "social", "bad": "other"}}), encoding="utf-8")
            self.assertEqual(collector.load_category_overrides(), {"p": "politics", "s": "social"})
        collector.MODERATION_FILE = old_file

    def test_youtube_local_filter_does_not_match_author_or_generated_summary(self):
        source = {"type": "youtube_channel", "include_keywords": ["Sóller", "Fornalutx"]}
        posts = [
            {"title": "Ballada a Palma", "summary": "Vídeo publicat per una entitat de Sóller.",
             "url": "https://www.youtube.com/watch?v=Soller"},
            {"title": "Ballada a Fornalutx", "summary": "", "url": "https://www.youtube.com/watch?v=local"},
            {"title": "Concert a So\u0301ller", "summary": "", "url": "https://www.youtube.com/watch?v=local2"},
        ]
        self.assertEqual(collector.filter_by_keywords(source, posts), posts[1:])

    def test_rss_local_filter_still_accepts_original_url(self):
        post = {"title": "Millores al municipi", "summary": "", "url": "https://example.test/noticies/soller"}
        self.assertEqual(collector.filter_by_keywords(
            {"type": "rss", "include_keywords": ["Soller"]}, [post]), [post])

    def test_video_dates_exclude_old_future_and_undated_posts(self):
        now = datetime.now(timezone.utc)
        posts = [
            {"id": "recent", "published_at": (now - timedelta(days=1)).isoformat()},
            {"id": "archive", "published_at": (now - timedelta(days=61)).isoformat()},
            {"id": "future", "published_at": (now + timedelta(days=1)).isoformat()},
            {"id": "undated", "published_at": None},
        ]
        self.assertEqual(collector.filter_by_max_age({"max_age_days": 60}, posts), posts[:1])

    def test_soller2010_keeps_original_dates_and_excludes_old_notices(self):
        config = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
        source = next(item for item in config["sources"] if item["id"] == "soller-2010")
        recent_url = source["url"] + "/recollida-selectiva-dies-de-recollida-i-com-reciclar-correctament"
        archive_url = source["url"] + "/apertura-piscines-son-angelats"
        # Dates publicades a la font original; les dues notícies encara surten al llistat.
        pages = {
            source["url"]: f'<a href="{recent_url}">Veure</a><a href="{archive_url}">Veure</a>',
            recent_url: "<h1>RECOLLIDA SELECTIVA</h1><p>06/08/2026 Notícia</p>",
            archive_url: "<h1>APERTURA PISCINES SON ANGELATS</h1><p>24/03/2026 Notícia</p>",
        }
        with patch.object(collector, "fetch_bytes", side_effect=lambda url, *_: (pages[url].encode(), "utf-8")):
            posts = collector.fetch_source(source)
        self.assertEqual([post["published_at"] for post in posts], [
            "2026-08-06T12:00:00+00:00", "2026-03-24T12:00:00+00:00",
        ])
        with patch.object(collector, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 9, 17, 14, tzinfo=timezone.utc)
            recent = collector.filter_by_max_age(source, posts)
        self.assertEqual([post["url"] for post in recent], [recent_url])

    def test_cultural_titles_do_not_create_municipal_claims(self):
        source = {"id": "youtube-cultural", "name": "Entitat cultural"}
        for title in ["Concert complet", "Sessió de música", "Joan Miquel Oliver"]:
            summary = collector.social_summary_from_title(source, title)
            self.assertNotIn("municipal", summary)
            self.assertNotIn("Retransmissió", summary)
        municipal = {"id": "youtube-ajuntament-soller", "name": "Ajuntament de Sóller"}
        self.assertIn("sessió plenària", collector.social_summary_from_title(municipal, "Ple ordinari"))

    def test_youtube_retains_original_metadata_without_copying_description_or_image(self):
        source = {"id": "youtube-cultural", "name": "Entitat cultural", "url": "https://www.youtube.com/feeds/videos.xml",
                  "type": "youtube_channel", "source_type": "social", "platform": "YouTube",
                  "account": "@cultural", "image_policy": "embed_only", "content_policy": "generated_social_summary"}
        feed = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
          <entry><title>Concert complet a Soller</title><published>2026-09-16T18:00:00Z</published>
          <link rel="alternate" href="https://www.youtube.com/watch?v=abcdefghijk"/>
          <media:group><media:description>Text original llarg que no s'ha de copiar.</media:description>
          <media:thumbnail url="https://example.test/protected.jpg"/></media:group></entry></feed>'''
        with patch.object(collector, "fetch_bytes", return_value=(feed, "utf-8")):
            post = collector.fetch_youtube_channel(source)[0]
        self.assertEqual(post["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(post["published_at"], "2026-09-16T18:00:00+00:00")
        self.assertEqual(post["account"], "@cultural")
        self.assertEqual(post["media_type"], "video")
        self.assertFalse(post["image_allowed"])
        self.assertNotIn("Text original", post["summary"])
        self.assertNotIn("media_url", post)

    def test_official_oembed_requires_explicit_policy_and_same_provider(self):
        source = {"id": "local-media", "name": "Mitjà local", "url": "https://local.test/feed/",
                  "source_type": "media", "image_policy": "official_oembed"}
        post = collector.build_post(source, "Titular", "", "https://local.test/noticia/", "2026-09-18T08:00:00Z")
        self.assertEqual(post["embed_type"], "official_oembed")
        self.assertEqual(post["embed_url"], "https://local.test/noticia/embed/")
        self.assertFalse(post["image_allowed"])

        external = collector.build_post(source, "Titular", "", "https://other.test/noticia/", "2026-09-18T08:00:00Z")
        self.assertNotIn("embed_url", external)
        disabled = collector.build_post({**source, "image_policy": "disabled_until_rights_verified"},
                                        "Titular", "", "https://local.test/noticia/", "2026-09-18T08:00:00Z")
        self.assertNotIn("embed_url", disabled)

        configured = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["sources"]
        enabled = {item["id"] for item in configured if item.get("image_policy") == "official_oembed"}
        self.assertEqual(enabled, {"sa-veu-soller", "mucbo-noticies", "can-prunera-noticies"})


class SourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ["SOURCES_FILE", "OUTPUT_FILE", "JS_OUTPUT_FILE", "MANUAL_POSTS_FILE", "MODERATION_FILE"]:
            self.enterContext(patch.object(collector, name, self.root / name))
        self.enterContext(patch.object(collector, "fetch_optional_meta_social_sources", return_value=([], [], [])))
        self.paused = {"id": "paused", "name": "Font pausada", "type": "rss", "enabled": False, "max_age_days": 60}
        self.active = {"id": "active", "name": "Font activa", "type": "rss", "enabled": True, "max_age_days": 60}
        self.write(collector.SOURCES_FILE, {"sources": [self.paused, self.active]})
        self.kept = self.post("kept", "paused", 10)
        self.fresh = self.post("fresh", "active", 1)
        self.fetch = self.enterContext(patch.object(collector, "fetch_source", return_value=[self.fresh]))

    def write(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def post(self, identifier, source, age):
        return {"id": identifier, "source_id": source, "source": source, "source_type": "official",
                "title": identifier, "category": "news", "summary": "",
                "published_at": (datetime.now(timezone.utc) - timedelta(days=age)).isoformat(),
                "url": f"https://example.test/{identifier}"}

    def collect(self):
        self.assertEqual(collector.main(), 0)
        return json.loads(collector.OUTPUT_FILE.read_text(encoding="utf-8"))

    def test_disabled_source_retains_visible_recent_posts_without_fetching(self):
        self.write(collector.OUTPUT_FILE, {"posts": [self.kept, self.post("old", "paused", 61),
            self.post("hidden", "paused", 1), self.post("removed-source", "removed", 1),
            self.post("active-cache", "active", 1)]})
        self.write(collector.MODERATION_FILE, {"hidden_post_ids": ["hidden"]})
        for _ in range(2):
            result = self.collect()
            self.assertEqual([post["id"] for post in result["posts"]], ["fresh", "kept"])
            kept = result["posts"][1]
            self.assertEqual(kept["published_at"], self.kept["published_at"])
            self.assertEqual(kept["url"], self.kept["url"])
            self.assertEqual(result["source_count"], 1)
            self.assertEqual([source["source_id"] for source in result["source_status"]], ["active"])
        self.assertEqual([call.args[0]["id"] for call in self.fetch.call_args_list], ["active", "active"])

    def test_moderation_can_hide_and_restore_a_retained_post(self):
        self.write(collector.OUTPUT_FILE, {"posts": [self.kept]})
        self.collect()
        spec = importlib.util.spec_from_file_location("manage_posts", ROOT / "scripts/manage_posts.py")
        moderation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(moderation)
        moderation.POSTS_FILE = collector.OUTPUT_FILE
        moderation.POSTS_JS_FILE = collector.JS_OUTPUT_FILE
        moderation.MODERATION_FILE = collector.MODERATION_FILE
        moderation.MANUAL_FILE = collector.MANUAL_POSTS_FILE
        moderation.POST_ID = self.kept["id"]
        moderation.hide()
        self.assertEqual([post["id"] for post in self.collect()["posts"]], ["fresh"])
        moderation.unhide()
        self.assertEqual([post["id"] for post in self.collect()["posts"]], ["fresh", "kept"])

    def test_reenabled_source_resumes_collection_without_duplicates(self):
        self.write(collector.OUTPUT_FILE, {"posts": [self.kept]})
        self.collect()
        self.paused["enabled"] = True
        self.write(collector.SOURCES_FILE, {"sources": [self.paused, self.active]})
        self.fetch.reset_mock()
        self.fetch.side_effect = lambda source: [self.kept, self.post("resumed", "paused", 2)] if source["id"] == "paused" else [self.fresh]
        result = self.collect()
        self.assertEqual([post["id"] for post in result["posts"]], ["fresh", "resumed", "kept"])
        self.assertEqual([call.args[0]["id"] for call in self.fetch.call_args_list], ["paused", "active"])

    def test_invalid_cache_is_not_overwritten_when_preservation_is_required(self):
        collector.OUTPUT_FILE.write_text("invalid JSON", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            collector.main()
        self.assertEqual(collector.OUTPUT_FILE.read_text(encoding="utf-8"), "invalid JSON")
        self.fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
