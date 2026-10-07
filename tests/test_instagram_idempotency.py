"""Reproduce accepted Meta publishes whose HTTP acknowledgement is lost.

All Graph requests are simulated; no social account is contacted or changed.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import publish_own_social as own, publish_collected_social as auto
from scripts import retry_manual_social as retry
from scripts.instagram_delivery import InstagramPublishUncertain


RATE_LIMIT = "Application request limit reached [code=4, subcode=2207051]"


class InstagramIdempotencyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        self.log_file = root / "social.json"
        self.url = "https://example.test/noticies/one.html"
        self.enterContext(patch.multiple(own, LOG_FILE=self.log_file, TOKEN="test-only",
            POST_ID="one", POST_URL=self.url, TITLE="Title", BODY="Body", SOURCE_NAME="",
            ORIGINAL_URL="", IMAGE_URL="https://example.test/card.jpg", CONFIRMATION="PUBLICAR",
            DO_FACEBOOK=False, DO_INSTAGRAM=True))
        self.enterContext(patch.multiple(auto, LOG_FILE=self.log_file, TOKEN="test-only"))
        for publisher in (own, auto):
            self.enterContext(patch.object(publisher, "discover_accounts",
                return_value=("page", "test-only", "ig", "soller.ara")))
            self.enterContext(patch.object(publisher, "graph", side_effect=self.graph))
        self.facebook = self.enterContext(patch.object(own, "publish_facebook", return_value="fb-id"))
        self.auto_facebook = self.enterContext(patch.object(auto, "publish_facebook", return_value="fb-id"))
        self.enterContext(patch.object(auto, "wait_public_image"))
        self.item = {"post_id": "one", "original_url": self.url, "source_id": "source",
                     "source": "Source", "image_url": "https://example.test/card.jpg",
                     "title": "Title", "summary": "Body", "platforms": ["facebook", "instagram"],
                     "category": "news", "published_at": datetime.now(timezone.utc).isoformat()}
        self.enterContext(patch.object(auto, "load_json", side_effect=self.auto_load))
        self.enterContext(patch.object(auto, "eligible_entries", return_value=[self.item]))
        self.media = []
        self.posts = 0
        self.containers = 0
        self.caption = ""
        self.response_error = None
        self.creation_error = None
        self.read_error = None
        self.write({"entries": []})

    def auto_load(self, path, fallback):
        if path == self.log_file:
            return self.read()
        if path == auto.CONFIG_FILE:
            return {"enabled": True}
        if path == auto.QUEUE_FILE:
            return {"enabled": True, "entries": [self.item]}
        return fallback

    def read(self):
        return json.loads(self.log_file.read_text())

    def write(self, log):
        self.log_file.write_text(json.dumps(log))

    def unpause(self):
        log = self.read()
        log.pop("cooldowns", None)
        self.write(log)

    def graph(self, path, method="GET", params=None, token=None):
        if path == "ig/media" and method == "GET":
            if self.read_error:
                raise self.read_error
            return {"data": list(self.media)}
        if path == "ig/media" and method == "POST":
            if self.creation_error:
                raise self.creation_error
            self.containers += 1
            self.caption = params["caption"]
            return {"id": "container"}
        if path == "container":
            return {"status_code": "FINISHED"}
        if path == "ig/media_publish" and method == "POST":
            # A durable local intent must exist BEFORE the publish reaches Meta.
            receipt = self.read()["entries"][-1]
            self.assertEqual(receipt["status"], "publishing")
            self.assertEqual(receipt["container_id"], params["creation_id"])
            self.posts += 1
            self.media.append({"id": "real-id", "caption": self.caption,
                               "permalink": "https://www.instagram.com/p/example/"})
            if self.response_error:
                raise self.response_error
            return {"id": "real-id"}
        if path == "real-id":
            return {"permalink": "https://www.instagram.com/p/example/"}
        raise AssertionError(f"Unexpected Graph request: {method} {path}")

    def test_accepted_manual_publish_with_rate_limit_is_reconciled_without_repeat(self):
        self.response_error = RuntimeError(RATE_LIMIT)
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.read()["entries"][-1]["status"], "verification_required")
        self.assertIn("code=4", self.read()["entries"][-1]["error"])
        self.unpause()
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.read()["entries"][-1]["remote_id"], "real-id")
        self.assertEqual(own.main(), 0)
        self.assertEqual((self.containers, self.posts), (1, 1))

    def test_timeout_and_delayed_visibility_do_not_create_another_container(self):
        self.response_error = TimeoutError("Response lost after Meta accepted the publish")
        self.assertEqual(own.main(), 1)
        delivered = self.media
        self.media = []  # Simulate eventual visibility in Instagram's GET endpoint.
        self.assertEqual(own.main(), 1)
        self.assertEqual((self.containers, self.posts), (1, 1))
        self.media = delivered
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.read()["entries"][-1]["status"], "success")
        self.assertEqual(self.posts, 1)

    def test_missing_log_after_runner_crash_still_reads_back_remote_post(self):
        self.media = [{"id": "real-id", "caption": f"Title\nNotícia completa: {self.url}\n"}]
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.read()["entries"][-1]["remote_id"], "real-id")
        self.assertEqual((self.containers, self.posts), (0, 0))

    def test_meta_limit_before_publish_can_retry_genuinely_unsent_post(self):
        self.creation_error = RuntimeError(RATE_LIMIT)
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.read()["entries"][-1]["status"], "deferred")
        self.assertEqual(self.posts, 0)
        self.unpause()
        self.creation_error = None
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.posts, 1)

    def test_unreadable_instagram_does_not_block_facebook_or_send_blindly(self):
        self.read_error = TimeoutError("Instagram read unavailable")
        with patch.object(own, "DO_FACEBOOK", True):
            self.assertEqual(own.main(), 0)
        self.facebook.assert_called_once()
        self.assertEqual((self.containers, self.posts), (0, 0))
        self.assertEqual(self.read()["entries"][-1]["status"], "deferred")
        self.read_error = None
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.posts, 1)

    def test_equal_title_of_another_article_does_not_suppress_new_publication(self):
        self.media = [{"id": "other", "caption": "Title\nhttps://example.test/noticies/another.html"}]
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.posts, 1)

    def test_runner_stopped_after_publish_leaves_intent_for_read_only_recovery(self):
        self.response_error = SystemExit("Runner stopped before saving acknowledgement")
        with self.assertRaises(SystemExit):
            own.main()
        self.assertEqual(self.read()["entries"][-1]["status"], "publishing")
        self.assertEqual(own.main(), 0)
        self.assertEqual(self.posts, 1)

    def test_automatic_publish_lost_response_does_not_repeat_either_platform(self):
        self.response_error = RuntimeError(RATE_LIMIT)
        self.assertEqual(auto.main(), 0)
        self.auto_facebook.assert_called_once()
        self.assertEqual(self.read()["entries"][-1]["status"], "verification_required")
        self.unpause()
        self.assertEqual(auto.main(), 0)
        self.assertEqual(auto.main(), 0)
        self.assertEqual(self.posts, 1)
        self.auto_facebook.assert_called_once()
        self.assertEqual({e["platform"] for e in self.read()["entries"] if e["status"] == "success"},
                         {"facebook", "instagram"})

    def test_automatic_uncertain_request_with_no_visible_receipt_is_not_repeated(self):
        self.response_error = TimeoutError("Response lost")
        self.assertEqual(auto.main(), 1)
        self.media = []
        self.assertEqual(auto.main(), 1)
        self.assertEqual((self.containers, self.posts), (1, 1))

    def test_automatic_read_back_remains_specific_to_source(self):
        self.media = [{"id": "other", "caption": f"Informació original: {self.url}\n\nFont: Other"}]
        self.assertEqual(auto.main(), 0)
        self.assertEqual(self.posts, 1)

    def test_trimmed_log_keeps_uncertain_intent_even_after_later_discovery_error(self):
        first = {"post_id": "one", "platform": "instagram", "status": "publishing",
                 "container_id": "container", "retry_requested": True}
        entries = [first, {"post_id": "one", "platform": "instagram", "status": "error"}]
        entries += [{"post_id": str(i), "platform": "instagram", "status": "error"} for i in range(1001)]
        log = {"entries": entries}
        auto.save_log(log)
        self.assertIn(first, self.read()["entries"])
        self.assertEqual([p["id"] for p in retry.pending_posts(self.read(),
                         [{"id": "one", "source_type": "own"}], set())], ["one"])


if __name__ == "__main__":
    unittest.main()
