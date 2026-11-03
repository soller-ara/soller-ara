import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from scripts import freenewsapi_client as api


class FreeNewsAPIClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state.json"
        self.now = datetime(2026, 11, 3, 8, tzinfo=timezone.utc)
        self.sources = [{"id": host, "type": "freenewsapi_search", "host": host,
                         "query_terms": ["Sóller", "Port de Sóller", "Fornalutx", "Biniaraix", "Deià", "Deia"]}
                        for host in ("www.diariodemallorca.es", "cronicabalear.es")]

    def client(self, **kwargs):
        return api.FreeNewsAPIClient(self.sources, self.state,
                                     api_key=kwargs.pop("api_key", "unit-test-key"),
                                     now=kwargs.pop("now", self.now), **kwargs)

    def results(self, term="Sóller"):
        return [{"title": term + " · Notícia", "url": "https://" + s["host"] + "/noticia",
                 "published_at": self.now.isoformat(), "lang": "ca"}
                for s in self.sources]

    def prime(self):
        client = self.client()
        with patch.object(api.FreeNewsAPIClient, "_request", side_effect=self.results), patch.object(api.time, "sleep"):
            client.results(self.sources[0])
        return client

    def test_missing_key_does_not_contact_provider_or_create_state(self):
        client = self.client(api_key="")
        with patch.object(client, "_request") as request:
            with self.assertRaisesRegex(RuntimeError, "FREENEWSAPI_KEY"):
                client.results(self.sources[0])
            request.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_two_publishers_share_queries_and_repeated_runs_use_cache(self):
        client = self.client()
        with patch.object(client, "_request", side_effect=self.results) as request, patch.object(api.time, "sleep"):
            first = client.results(self.sources[0])
            second = client.results(self.sources[1])
            self.assertEqual(request.call_count, 6)
        self.assertTrue(all("diariodemallorca.es" in x["url"] for x in first))
        self.assertTrue(all("cronicabalear.es" in x["url"] for x in second))
        again = self.client(now=self.now + timedelta(minutes=20))
        with patch.object(again, "_request") as request:
            self.assertEqual(again.results(self.sources[0]), first)
            request.assert_not_called()
        self.assertNotIn("unit-test-key", self.state.read_text())

    def test_rotates_all_terms_within_two_hours_without_manual_extra_calls(self):
        self.prime()
        seen = []
        for hour in (1, 2):
            client = self.client(now=self.now + timedelta(hours=hour))
            with patch.object(client, "_request", side_effect=lambda t: seen.append(t) or self.results(t)), patch.object(api.time, "sleep"):
                client.results(self.sources[0])
            same_hour = self.client(now=self.now + timedelta(hours=hour, minutes=10))
            with patch.object(same_hour, "_request") as request:
                same_hour.results(self.sources[1])
                request.assert_not_called()
        self.assertCountEqual(seen, self.sources[0]["query_terms"])

    def test_full_31_day_schedule_stays_below_free_plan(self):
        self.now = datetime(2026, 12, 1, tzinfo=timezone.utc)
        calls = 0
        def fetch(term):
            nonlocal calls
            calls += 1
            return self.results(term)
        with patch.object(api.FreeNewsAPIClient, "_request", side_effect=fetch), patch.object(api.time, "sleep"):
            for hour in range(31 * 24):
                client = self.client(now=self.now + timedelta(hours=hour))
                client.results(self.sources[0])
                client.results(self.sources[1])
        self.assertEqual(calls, 2235)
        self.assertLess(calls, 2700)

    def test_delayed_collection_refreshes_all_terms_with_accumulated_credits(self):
        self.prime()
        client = self.client(now=self.now + timedelta(hours=2, minutes=15))
        with patch.object(client, "_request", side_effect=self.results) as request, patch.object(api.time, "sleep"):
            client.results(self.sources[0])
        self.assertEqual(request.call_count, 6)
        self.assertEqual(client.status()["api_oldest_query_checked_at"], client.now.isoformat())

    def test_monthly_stop_and_corrupt_ledger_do_not_make_requests(self):
        self.prime()
        data = json.loads(self.state.read_text())
        data["requests_this_month"] = 2700
        self.state.write_text(json.dumps(data))
        with patch.object(api.FreeNewsAPIClient, "_request") as request:
            with self.assertRaisesRegex(RuntimeError, "2.700"):
                self.client(now=self.now + timedelta(hours=1)).results(self.sources[0])
            self.state.write_text("{invalid")
            with self.assertRaisesRegex(RuntimeError, "registre de quota invàlid"):
                self.client().results(self.sources[0])
            request.assert_not_called()
        self.assertEqual(self.state.read_text(), "{invalid")

    def test_unauthorized_consumes_one_request_and_does_not_repeat_for_second_source(self):
        opener = unittest.mock.MagicMock()
        opener.open.side_effect = HTTPError(api.API_URL, 401, "unit-test-key", {}, io.BytesIO(b"unit-test-key"))
        client = self.client()
        with patch.object(api, "build_opener", return_value=opener):
            for source in self.sources:
                with self.assertRaisesRegex(RuntimeError, "FREENEWSAPI_KEY") as result:
                    client.results(source)
                self.assertNotIn("unit-test-key", str(result.exception))
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(json.loads(self.state.read_text())["requests_this_month"], 1)

    def test_authenticated_request_keeps_only_allowed_metadata_and_hosts(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        data = self.results() + [
            {"title": "Wrong", "url": "https://evil.test/soller", "published_at": self.now.isoformat()},
            {"title": "No date", "url": "https://cronicabalear.es/no-date"},
        ]
        data[0].update(description="Do not copy", image="https://evil.test/picture.jpg", text="Body")
        response.read.return_value = json.dumps({"results": data}).encode()
        opener = unittest.mock.MagicMock()
        opener.open.return_value = response
        client = self.client()
        with patch.object(api, "build_opener", return_value=opener):
            result = client._request("Sóller")
        self.assertEqual(len(result), 2)
        self.assertTrue(all(set(x) == {"title", "url", "published_at", "lang"} for x in result))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer unit-test-key")
        self.assertNotIn("unit-test-key", request.full_url)
        query = parse_qs(urlparse(request.full_url).query)
        self.assertIn("cronicabalear.es", query["host"][0])
        self.assertIn("www.diariodemallorca.es", query["host"][0])
        self.assertEqual(query["full_text"], ["false"])

    def test_invalid_json_is_not_a_successful_empty_feed(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"unrelated": []}'
        opener = unittest.mock.MagicMock()
        opener.open.return_value = response
        with patch.object(api, "build_opener", return_value=opener):
            with self.assertRaisesRegex(RuntimeError, "resposta no vàlida"):
                self.client()._request("Sóller")

    def test_redirect_cannot_forward_authorization_to_another_host(self):
        self.assertIsNone(api.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test/"))


if __name__ == "__main__":
    unittest.main()
