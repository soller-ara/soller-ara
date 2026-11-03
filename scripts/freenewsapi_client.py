"""Authenticated, shared news searches with a persistent Free-plan budget.

Only headline/date/link metadata is cached. Never persist the API key or response
bodies. The collection workflow's existing global lock serializes this state.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_URL = "https://freenewsapi.ai/v1/search"
MONTHLY_LIMIT = 2700  # Leave 300 of the provider's 3,000 requests in reserve.
HOURLY_LIMIT = 3
BURST_LIMIT = 6


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A provider redirect must not send the Authorization header elsewhere.
        return None


class FreeNewsAPIClient:
    def __init__(self, sources, state_file: Path, *, api_key=None, now=None):
        self.sources = [s for s in sources if s.get("enabled", True)
                        and s.get("type") == "freenewsapi_search"]
        self.state_file = state_file
        self.api_key = (os.environ.get("FREENEWSAPI_KEY", "")
                        if api_key is None else api_key).strip()
        self.now = now or datetime.now(timezone.utc)
        self.terms = list(dict.fromkeys(str(t).strip() for s in self.sources
                                       for t in s.get("query_terms", []) if str(t).strip()))
        self.hosts = sorted({alias for s in self.sources if s.get("host")
                             for alias in (s["host"].lower(),
                                           s["host"].lower().removeprefix("www."),
                                           "www." + s["host"].lower().removeprefix("www."))})
        self.state = None
        self.error = None
        self.prepared = False

    def _load(self):
        state = {"version": 1, "month": self.now.strftime("%Y-%m"),
                 "requests_this_month": 0, "credits": float(BURST_LIMIT),
                 "refilled_at": self.now.isoformat(), "queries": {}}
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                if (state.get("version") != 1 or not isinstance(state.get("queries"), dict)
                        or not isinstance(state.get("month"), str)
                        or type(state.get("requests_this_month")) is not int
                        or state["requests_this_month"] < 0
                        or type(state.get("credits")) not in (int, float)
                        or not 0 <= state["credits"] <= BURST_LIMIT):
                    raise ValueError()
                refilled = datetime.fromisoformat(state["refilled_at"])
                if refilled.tzinfo is None or refilled > self.now:
                    raise ValueError()
                for entry in state["queries"].values():
                    if not isinstance(entry, dict) or not isinstance(entry.get("results"), list):
                        raise ValueError()
                    checked = datetime.fromisoformat(entry["checked_at"])
                    if checked.tzinfo is None or checked > self.now:
                        raise ValueError()
            except (ValueError, TypeError, KeyError, AttributeError):
                raise RuntimeError("Free News API: registre de quota invàlid; no es reinicia ni es consulta.") from None
        if state["month"] != self.now.strftime("%Y-%m"):
            state.update(month=self.now.strftime("%Y-%m"), requests_this_month=0)
        elapsed = (self.now - datetime.fromisoformat(state["refilled_at"])).total_seconds()
        state["credits"] = min(BURST_LIMIT, state["credits"] + elapsed * HOURLY_LIMIT / 3600)
        state["refilled_at"] = self.now.isoformat()
        self.state = state

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.state_file)

    def _request(self, term):
        params = {"host": ",".join(self.hosts), "q": term, "size": 100,
                  "date": "30d", "sort": "date", "full_text": "false",
                  "fields": "title,url,published_at,lang"}
        request = Request(API_URL + "?" + urlencode(params), headers={
            "Authorization": "Bearer " + self.api_key, "Accept": "application/json",
            "User-Agent": "SollerAra/0.62 (+https://soller-ara.github.io/soller-ara/)",
        })
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ValueError()
        except HTTPError as exc:
            if exc.code == 401:
                message = "clau absent o no vàlida; revisau el secret FREENEWSAPI_KEY de GitHub"
            elif exc.code == 429:
                message = "el proveïdor limita les consultes; es conserven les entrades anteriors"
            else:
                message = f"HTTP {exc.code}; es conserven les entrades anteriors"
            raise RuntimeError("Free News API: " + message + ".") from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError("Free News API: connexió no disponible; es conserven les entrades anteriors.") from None
        except (ValueError, UnicodeError):
            raise RuntimeError("Free News API: resposta no vàlida; es conserven les entrades anteriors.") from None

        results = []
        for item in data["results"]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlparse(url)
            if (parsed.scheme != "https" or parsed.netloc.lower() not in self.hosts
                    or not all(isinstance(item.get(k), str) and item[k].strip()
                               for k in ("title", "published_at"))):
                continue
            results.append({k: item.get(k, "") for k in ("title", "url", "published_at", "lang")})
        return results

    def _prepare(self):
        if self.prepared:
            if self.error:
                raise RuntimeError(self.error)
            return
        self.prepared = True
        try:
            if not self.api_key:
                raise RuntimeError("Free News API: falta configurar el secret FREENEWSAPI_KEY de GitHub; no es fan consultes.")
            if not self.terms or not self.hosts:
                raise RuntimeError("Free News API: configuració de fonts incompleta.")
            self._load()
            if self.state["requests_this_month"] >= MONTHLY_LIMIT:
                raise RuntimeError("Free News API: límit preventiu de 2.700 consultes mensuals assolit.")
            queries = self.state["queries"]
            # Three shared queries/hour on average, with six credits in reserve.
            # A delayed cron can refresh all six terms without losing coverage.
            available = min(int(self.state["credits"]),
                            MONTHLY_LIMIT - self.state["requests_this_month"])
            ordered = sorted(self.terms, key=lambda t: queries.get(t, {}).get("checked_at", ""))
            due = [t for t in ordered if (t not in queries or
                   (self.now - datetime.fromisoformat(queries[t]["checked_at"])).total_seconds() >= 3600)]
            for index, term in enumerate(due[:max(0, available)]):
                if index:
                    time.sleep(0.6)  # Free plan: no more than two requests/second.
                # Reserve before contacting the provider: failed requests count,
                # and workflow retries/manual runs must share the same budget.
                self.state["requests_this_month"] += 1
                self.state["credits"] -= 1
                self._save()
                results = self._request(term)
                queries[term] = {"checked_at": self.now.isoformat(), "results": results}
                self._save()
            if any(t not in queries for t in self.terms):
                raise RuntimeError("Free News API: primera lectura incompleta; es reprendrà dins la quota horària.")
        except Exception as exc:
            self.error = str(exc)
            raise

    def results(self, source):
        self._prepare()
        host = source["host"].lower().removeprefix("www.")
        results = {}
        for term in source.get("query_terms", []):
            for item in self.state["queries"].get(term, {}).get("results", []):
                parsed = urlparse(item.get("url", ""))
                if parsed.scheme == "https" and parsed.netloc.lower().removeprefix("www.") == host:
                    results[item["url"]] = item
        return list(results.values())

    def status(self):
        checked = [self.state["queries"][t]["checked_at"] for t in self.terms]
        return {"api_oldest_query_checked_at": min(checked),
                "api_latest_query_checked_at": max(checked),
                "api_requests_this_month": self.state["requests_this_month"],
                "api_monthly_limit": MONTHLY_LIMIT}
