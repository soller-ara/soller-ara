import unittest
from unittest.mock import Mock
from scripts.instagram_delivery import matching_media, read_account_media


class InstagramDeliveryTests(unittest.TestCase):
    def test_exact_article_link_distinguishes_other_posts_and_url_prefixes(self):
        url = "https://example.test/noticies/one.html"
        media = [{"id": str(i), "caption": caption} for i, caption in enumerate([
            f"Title\nNotícia completa: {url}\nLinks", f"Edited title\n{url}",
            "Title\nhttps://example.test/noticies/two.html", url + "?other=1", url + "extra",
        ])]
        self.assertEqual([item["id"] for item in matching_media(media, url)], ["0", "1"])

    def test_paginated_reads_never_follow_urls_containing_credentials(self):
        graph = Mock(side_effect=[{"data": [{"id": "one"}], "paging": {
            "next": "https://graph.example/media?access_token=do-not-use", "cursors": {"after": "cursor"}}},
            {"data": [{"id": "two"}]}])
        self.assertEqual(len(read_account_media(graph, "account", "test-only")), 2)
        for call in graph.call_args_list:
            self.assertEqual(call.args, ("account/media",))
            self.assertNotIn("method", call.kwargs)
            self.assertNotIn("access_token", call.kwargs["params"])
        self.assertEqual(graph.call_args_list[1].kwargs["params"]["after"], "cursor")

    def test_unreadable_and_incomplete_lists_fail_closed(self):
        for payload in [{}, {"data": "broken"}, {"data": [{}], "paging": {"next": "more"}},
                        {"data": [], "paging": {"next": "more", "cursors": {"after": "cursor"}}}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                read_account_media(Mock(return_value=payload), "account", "test-only")
        with self.assertRaises(ValueError):
            read_account_media(Mock(return_value={"data": [{"id": "one"}], "paging": {
                "next": "more", "cursors": {"after": "cursor"}}}), "account", "test-only", max_pages=1)


if __name__ == "__main__":
    unittest.main()
