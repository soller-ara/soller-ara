import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SocialDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prepare = module("prepare_collected_social")
        self.publish = module("publish_collected_social")
        for name in ["CONFIG_FILE", "POSTS_FILE", "LOG_FILE", "QUEUE_FILE", "SOURCES_FILE", "MODERATION_FILE"]:
            path = self.root / f"{name}.json"
            setattr(self.prepare, name, path)
            setattr(self.publish, name, path)
        self.prepare.CARD_DIR = self.root / "cards"
        self.config = {"enabled": True, "platforms": {"facebook": True, "instagram": True},
                       "max_posts_per_run": 3, "max_age_hours": 6, "one_post_per_source_per_run": True,
                       "sources": {s: {"facebook": True, "instagram": True} for s in ["a", "b", "c", "d", "off"]}}
        self.write(self.prepare.CONFIG_FILE, self.config)
        self.write(self.prepare.SOURCES_FILE, {"sources": [{"id": s, "enabled": s != "off"} for s in self.config["sources"]]})
        self.write(self.prepare.MODERATION_FILE, {"hidden_post_ids": ["hidden"]})
        self.write(self.prepare.LOG_FILE, {"version": 1, "entries": []})

    def write(self, path, value):
        path.write_text(json.dumps(value))

    def post(self, identifier, source="a", age=1, **extra):
        return {"id": identifier, "source_id": source, "source": "Font de prova", "source_type": "media",
                "title": "Notícia de prova", "published_at": (datetime.now(timezone.utc)-timedelta(hours=age)).isoformat(),
                "category": "news", "url": f"https://example.test/{identifier}", "content_policy": "headline_date_link_only",
                "summary": "Aquest text no s'ha de reutilitzar.", **extra}

    def prepare_posts(self, posts):
        self.write(self.prepare.POSTS_FILE, {"posts": posts})
        with patch.object(self.prepare, "generate_card", return_value="https://example.test/card.jpg"):
            self.assertEqual(self.prepare.main(), 0)
        return json.loads(self.prepare.QUEUE_FILE.read_text())["entries"]

    def test_selection_obeys_age_moderation_sources_and_limits(self):
        items = [self.post("future", age=-1), self.post("hidden"), self.post("inactive", "off"),
                 self.post("old", age=7), self.post("own", source_type="own"),
                 self.post("a1", age=.1), self.post("a2", age=.2), self.post("b1", "b", .3),
                 self.post("c1", "c", .4), self.post("d1", "d", .5)]
        selected = self.prepare_posts(items)
        self.assertEqual([p["post_id"] for p in selected], ["a1", "b1", "c1"])
        self.assertEqual(self.publish.safe_summary(selected[0]), "")
        self.assertIn("Font: Font de prova", self.publish.base_text(selected[0]))
        self.assertIn("https://example.test/a1", self.publish.base_text(selected[0]))

    def test_success_stays_deduplicated_after_later_error(self):
        log = {"entries": [{"post_id": "a1", "platform": "facebook", "status": status} for status in ["success", "error"]]}
        self.write(self.prepare.LOG_FILE, log)
        selected = self.prepare_posts([self.post("a1")])
        self.assertEqual(selected[0]["platforms"], ["instagram"])
        self.assertTrue(self.publish.already_published(log, "a1", "facebook"))

    def test_headline_change_does_not_resend_same_source_url(self):
        old = self.post("old")
        changed = self.post("new", title="Titular editat", url=old["url"])
        log = {"entries": [{"post_id": "old", "source_id": "a", "post_url": old["url"],
                            "platform": "facebook", "status": "success"}]}
        self.write(self.prepare.LOG_FILE, log)
        selected = self.prepare_posts([changed])
        self.assertEqual(selected[0]["platforms"], ["instagram"])
        stale = [{**selected[0], "platforms": ["facebook", "instagram"]}]
        self.assertEqual(self.publish.eligible_entries(self.config, stale, log)[0]["platforms"], ["instagram"])
        log["entries"].append({**log["entries"][0], "platform": "instagram"})
        self.write(self.prepare.LOG_FILE, log)
        self.assertEqual(self.prepare_posts([changed]), [])
        self.assertEqual(self.publish.eligible_entries(self.config, stale, log), [])

    def test_url_deduplication_is_specific_to_source_and_platform(self):
        shared_url = "https://example.test/shared"
        log = {"entries": [{"post_id": "old", "source_id": "a", "post_url": shared_url,
                            "platform": "facebook", "status": "success"}]}
        self.write(self.prepare.LOG_FILE, log)
        queue = self.prepare_posts([self.post("different-source", source="b", url=shared_url)])
        self.assertEqual(queue[0]["platforms"], ["facebook", "instagram"])

    def test_instagram_caption_keeps_full_original_url(self):
        item = self.post("a1")
        item["image_url"] = "https://example.test/card.jpg"
        item["original_url"] = item["url"]
        item["content_policy"] = "summary_allowed"
        calls = []

        def fake_graph(path, **kwargs):
            calls.append((path, kwargs))
            if path == "ig/media":
                return {"id": "container"}
            if path == "container":
                return {"status_code": "FINISHED"}
            return {"id": "media"}

        with patch.object(self.publish, "wait_public_image"), patch.object(self.publish, "graph", side_effect=fake_graph):
            self.assertEqual(self.publish.publish_instagram(item, "ig", "soller.ara", "token"), "media")

        caption = calls[0][1]["params"]["caption"]
        self.assertIn(f"Informació original: {item['url']}", caption)
        self.assertLess(caption.index("Informació original:"), caption.index("Aquest text"))

    def test_changed_source_or_platform_is_rechecked_before_send(self):
        selected = self.prepare_posts([self.post("a1")])
        self.write(self.prepare.SOURCES_FILE, {"sources": [{"id": "a", "enabled": False}]})
        self.assertEqual(self.publish.eligible_entries(self.config, selected, {}), [])
        self.write(self.prepare.SOURCES_FILE, {"sources": [{"id": "a", "enabled": True}]})
        config = copy.deepcopy(self.config)
        config["platforms"]["facebook"] = False
        self.assertEqual(self.publish.eligible_entries(config, selected, {})[0]["platforms"], ["instagram"])

    def test_failed_instagram_retry_does_not_repeat_facebook(self):
        self.prepare_posts([self.post("a1")])
        with patch.object(self.publish, "TOKEN", "test-only"), \
             patch.object(self.publish, "discover_accounts", return_value=("page", "test-only", "ig", "soller.ara")), \
             patch.object(self.publish, "publish_facebook", return_value="page_post") as fb, \
             patch.object(self.publish, "publish_instagram", side_effect=RuntimeError("Simulated failure")):
            self.assertEqual(self.publish.main(), 1)
            fb.assert_called_once()
        log = json.loads(self.publish.LOG_FILE.read_text())
        self.assertEqual([x["status"] for x in log["entries"]], ["success", "error"])
        with patch.object(self.publish, "TOKEN", "test-only"), \
             patch.object(self.publish, "discover_accounts", return_value=("page", "test-only", "ig", "soller.ara")), \
             patch.object(self.publish, "publish_facebook") as fb, \
             patch.object(self.publish, "publish_instagram", return_value="ig_post") as ig, \
             patch.object(self.publish, "graph", side_effect=RuntimeError("Permalink temporarily unavailable")):
            self.assertEqual(self.publish.main(), 0)
            fb.assert_not_called()
            ig.assert_called_once()
        self.assertEqual(json.loads(self.publish.LOG_FILE.read_text())["entries"][-1]["status"], "success")

    def test_instagram_rate_limit_pauses_only_instagram(self):
        self.prepare_posts([self.post("a1"), self.post("b1", source="b")])
        rate_limit = RuntimeError("Application request limit reached [code=4, subcode=2207051]")
        with patch.object(self.publish, "TOKEN", "test-only"), \
             patch.object(self.publish, "discover_accounts", return_value=("page", "test-only", "ig", "soller.ara")), \
             patch.object(self.publish, "publish_facebook", return_value="page_post") as fb, \
             patch.object(self.publish, "publish_instagram", side_effect=rate_limit):
            self.assertEqual(self.publish.main(), 0)
            self.assertEqual(fb.call_count, 2)

        log = json.loads(self.publish.LOG_FILE.read_text())
        self.assertIn("instagram_until", log["cooldowns"])
        self.assertFalse(any(x["platform"] == "instagram" and x["status"] == "error" for x in log["entries"]))

        with patch.object(self.publish, "TOKEN", "test-only"), \
             patch.object(self.publish, "discover_accounts") as accounts, \
             patch.object(self.publish, "publish_facebook") as fb, \
             patch.object(self.publish, "publish_instagram") as ig:
            self.assertEqual(self.publish.main(), 0)
            accounts.assert_not_called()
            fb.assert_not_called()
            ig.assert_not_called()

    def test_missing_token_records_error_without_publishing(self):
        self.prepare_posts([self.post("a1")])
        with patch.object(self.publish, "TOKEN", ""), patch.object(self.publish, "graph") as graph:
            self.assertEqual(self.publish.main(), 1)
            graph.assert_not_called()
        self.assertEqual(len(json.loads(self.publish.LOG_FILE.read_text())["entries"]), 2)

    def test_instagram_pause_does_not_block_next_facebook_post_from_same_source(self):
        first, second = self.post("first", age=0.5), self.post("second", age=1)
        log = {"entries": [{"post_id": "first", "platform": "facebook", "status": "success"}],
               "cooldowns": {"instagram_until": (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}}
        self.write(self.prepare.LOG_FILE, log)
        queue = self.prepare_posts([first, second])
        self.assertEqual([p["post_id"] for p in queue], ["second"])
        self.assertEqual(queue[0]["platforms"], ["facebook"])
        # Revalidate a queue built before the pause began, applying quotas afterwards.
        stale = [{**first, "post_id": "first", "platforms": ["instagram"]},
                 {**second, "post_id": "second", "platforms": ["facebook", "instagram"]}]
        selected = self.publish.eligible_entries(self.config, stale, log)
        self.assertEqual([p["post_id"] for p in selected], ["second"])
        self.assertEqual(selected[0]["platforms"], ["facebook"])
        log["cooldowns"]["instagram_until"] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        selected = self.publish.eligible_entries(self.config, stale, log)
        self.assertEqual(selected[0]["post_id"], "first")
        self.assertEqual(selected[0]["platforms"], ["instagram"])

    def test_expired_archived_or_unverified_alerts_are_not_queued(self):
        until = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        posts = [self.post("expired", alert_status="expired", alert_valid_until=until),
                 self.post("archived", alert_status="archived"),
                 self.post("unverified", alert_status="unverified"),
                 self.post("stale-active", alert_status="active", alert_valid_until=until)]
        self.assertEqual(self.prepare_posts(posts), [])

    def test_warning_expiring_after_preparation_is_not_published(self):
        until = (datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        queue = self.prepare_posts([self.post("warning", alert_status="active", alert_valid_until=until)])
        self.assertEqual(queue[0]["alert_valid_until"], until)
        queue[0]["alert_valid_until"] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        self.write(self.prepare.QUEUE_FILE, {"enabled": True, "entries": queue})
        with patch.object(self.publish, "TOKEN", "test-only"), patch.object(self.publish, "discover_accounts") as accounts:
            self.assertEqual(self.publish.main(), 0)
            accounts.assert_not_called()

    def test_warning_expiring_after_facebook_is_not_sent_to_instagram(self):
        until = (datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        self.prepare_posts([self.post("warning", alert_status="active", alert_valid_until=until)])
        def facebook(item, *args):
            item["alert_valid_until"] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
            return "page_post"
        with patch.object(self.publish, "TOKEN", "test-only"), \
             patch.object(self.publish, "discover_accounts", return_value=("page", "test-only", "ig", "soller.ara")), \
             patch.object(self.publish, "publish_facebook", side_effect=facebook) as fb, \
             patch.object(self.publish, "publish_instagram") as ig:
            self.assertEqual(self.publish.main(), 0)
            fb.assert_called_once()
            ig.assert_not_called()


if __name__ == "__main__":
    unittest.main()
