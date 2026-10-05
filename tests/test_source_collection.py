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
    def test_aemet_filters_zone_before_limiting_rss_items(self):
        source = {"id": "aemet", "name": "AEMET", "type": "aemet_alerts",
                  "url": "https://example.test/rss", "filter_zone_codes": ["645401"], "max_items": 2}
        def item(code, number):
            return f'<item><title>Aviso {number}</title><link>https://example.test/{code}/{number}</link><pubDate>Mon, 05 Oct 2026 03:13:05 GMT</pubDate></item>'
        payload = ('<rss><channel>' + ''.join(item("999999", n) for n in range(98))
                   + ''.join(item("645401", n) for n in range(3)) + '</channel></rss>').encode()
        with patch.object(collector, "fetch_bytes", return_value=(payload, "utf-8")):
            posts = collector.fetch_aemet_alerts(source)
        self.assertEqual(len(posts), 2)
        self.assertTrue(all("645401" in post["url"] for post in posts))
        self.assertTrue(all(post["alert_status"] == "unverified" for post in posts))

    def test_manual_link_without_title_survives_automatic_refresh(self):
        link = {
            "id": "manual-link", "title": "", "summary": "",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "original_url": "https://www.facebook.com/story.php?story_fbid=123&id=456",
            "category": "agenda", "show_in_now": False,
            "content_policy": "manual_link_reference",
        }
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            manual = folder / "manual_posts.json"
            sources = folder / "sources.json"
            output = folder / "posts.json"
            manual.write_text(json.dumps({"posts": [
                link,
                {**link, "id": "empty-own", "original_url": ""},
                {**link, "id": "invalid-link", "original_url": "javascript:alert(1)"},
            ]}), encoding="utf-8")
            sources.write_text(json.dumps({"sources": []}), encoding="utf-8")
            with patch.multiple(collector, MANUAL_POSTS_FILE=manual,
                                SOURCES_FILE=sources, OUTPUT_FILE=output,
                                JS_OUTPUT_FILE=folder / "posts.js",
                                MODERATION_FILE=folder / "moderation.json"), \
                 patch.object(collector, "fetch_optional_meta_social_sources",
                              return_value=([], [], [])):
                self.assertEqual(collector.main(), 0)
            posts = json.loads(output.read_text(encoding="utf-8"))["posts"]
            self.assertEqual([post["id"] for post in posts], ["manual-link"])
            self.assertEqual(posts[0]["original_url"], link["original_url"])
            self.assertEqual(posts[0]["title"], "")
            self.assertEqual(posts[0]["category"], "agenda")
            self.assertFalse(posts[0]["show_in_now"])

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
        self.assertEqual(enabled, {'mucbo-noticies', 'can-prunera-noticies', 'futbol-balear-cf-soller', 'fora-vila-soller', 'sa-veu-soller'})


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

    def test_active_source_failure_retains_recent_data_and_reports_error(self):
        self.write(collector.OUTPUT_FILE, {"posts": [self.kept, self.fresh,
            self.post("old", "active", 61), self.post("hidden", "active", 1)]})
        self.write(collector.MODERATION_FILE, {"hidden_post_ids": ["hidden"],
            "category_overrides": {"fresh": "culture"}})
        self.fetch.side_effect = RuntimeError("HTTP 404")
        result = self.collect()
        self.assertEqual([post["id"] for post in result["posts"]], ["fresh", "kept"])
        self.assertEqual(result["posts"][0]["published_at"], self.fresh["published_at"])
        self.assertEqual(result["posts"][0]["category"], "culture")
        self.assertFalse(result["source_status"][0]["ok"])
        self.assertEqual(result["source_status"][0]["error"], "HTTP 404")
        self.assertEqual(result["source_status"][0]["retained_count"], 2)
        self.fetch.side_effect = None
        self.fetch.return_value = [self.fresh]
        self.assertEqual([post["id"] for post in self.collect()["posts"]], ["fresh", "kept"])

    def test_successful_empty_source_does_not_retain_stale_cache(self):
        self.write(collector.OUTPUT_FILE, {"posts": [self.fresh]})
        self.fetch.return_value = []
        result = self.collect()
        self.assertEqual(result["posts"], [])
        self.assertTrue(result["source_status"][0]["ok"])

    def test_aemet_empty_feed_retains_expired_history_without_changing_dates(self):
        self.active["type"] = "aemet_alerts"
        self.write(collector.SOURCES_FILE, {"sources": [self.active]})
        original = {**self.fresh, "category": "alerts",
                    "summary": "De 06:00 05-10-2026 CEST (UTC+2) a 08:59 05-10-2026 CEST (UTC+2)."}
        self.write(collector.OUTPUT_FILE, {"posts": [original]})
        self.fetch.return_value = []
        for _ in range(2):
            result = self.collect()
            self.assertEqual(len(result["posts"]), 1)
            post = result["posts"][0]
            self.assertEqual(post["id"], original["id"])
            self.assertEqual(post["published_at"], original["published_at"])
            self.assertEqual(post["alert_valid_until"], "2026-10-05T06:59:00+00:00")
            self.assertFalse(post["alert_in_feed"])
            self.assertEqual(result["source_status"][0]["archived_count"], 1)
        self.fetch.return_value = [original]
        result = self.collect()
        self.assertEqual(len(result["posts"]), 1)
        self.assertTrue(result["posts"][0]["alert_in_feed"])
        self.assertEqual(result["source_status"][0]["archived_count"], 0)

    def test_aemet_fetch_failure_marks_future_warning_unverified(self):
        self.active["type"] = "aemet_alerts"
        self.write(collector.SOURCES_FILE, {"sources": [self.active]})
        original = {**self.fresh, "alert_valid_until": (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()}
        self.write(collector.OUTPUT_FILE, {"posts": [original]})
        self.fetch.side_effect = RuntimeError("HTTP 503")
        result = self.collect()
        self.assertEqual(result["posts"][0]["alert_status"], "unverified")
        self.assertFalse(result["source_status"][0]["ok"])

    def test_invalid_manual_or_moderation_file_preserves_existing_feed(self):
        for path in [collector.MANUAL_POSTS_FILE, collector.MODERATION_FILE]:
            with self.subTest(file=path.name):
                self.write(collector.OUTPUT_FILE, {"posts": [self.fresh]})
                before = collector.OUTPUT_FILE.read_text()
                path.write_text("broken JSON")
                with self.assertRaises(json.JSONDecodeError):
                    collector.main()
                self.assertEqual(collector.OUTPUT_FILE.read_text(), before)
                self.fetch.assert_not_called()
                path.unlink()

    def test_invalid_cache_is_not_overwritten_when_preservation_is_required(self):
        collector.OUTPUT_FILE.write_text("invalid JSON", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            collector.main()
        self.assertEqual(collector.OUTPUT_FILE.read_text(encoding="utf-8"), "invalid JSON")
        self.fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
