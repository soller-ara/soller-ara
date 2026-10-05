"""Publication state shared by the collector and social queue.

A source's alert lifetime is distinct from its publication date. Past alerts
remain in the website archive but must not become fresh social warnings.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def instagram_is_paused(log: dict, now: datetime | None = None) -> bool:
    until = parse_timestamp((log.get("cooldowns") or {}).get("instagram_until"))
    return bool(until and (now or datetime.now(timezone.utc)) < until)


def aemet_period(summary: str) -> dict[str, str]:
    """Read the explicit UTC offsets in the original AEMET RSS description."""
    pattern = r"(\d{2}:\d{2})\s+(\d{2}-\d{2}-\d{4})\s+(?:CEST|CET)\s*\(UTC([+-]\d{1,2})(?::(\d{2}))?\)"
    matches = list(re.finditer(pattern, str(summary)))
    if len(matches) != 2:
        return {}
    dates = []
    try:
        for match in matches:
            hour_offset = int(match[3])
            minute_offset = int(match[4] or 0) * (-1 if match[3].startswith("-") else 1)
            offset = timezone(timedelta(hours=hour_offset, minutes=minute_offset))
            date = datetime.strptime(f"{match[2]} {match[1]}", "%d-%m-%Y %H:%M").replace(tzinfo=offset)
            dates.append(date.astimezone(timezone.utc))
    except ValueError:
        return {}
    if dates[1] <= dates[0]:
        return {}
    return {"alert_valid_from": dates[0].isoformat(), "alert_valid_until": dates[1].isoformat()}


def aemet_post_state(post: dict, *, in_feed: bool, verified: bool = True,
                     now: datetime | None = None) -> dict:
    result = dict(post)
    result.update(aemet_period(result.get("summary") or ""))
    start = parse_timestamp(result.get("alert_valid_from"))
    end = parse_timestamp(result.get("alert_valid_until"))
    current = now or datetime.now(timezone.utc)
    if end and end <= current:
        state = "expired"
    elif not verified:
        state = "unverified"
    elif not in_feed:
        state = "archived"
    elif not end:
        state = "unverified"
    elif start and start > current:
        state = "scheduled"
    else:
        state = "active"
    result.update({"alert_status": state, "alert_in_feed": in_feed})
    return result


def alert_can_be_published(post: dict, now: datetime | None = None) -> bool:
    state = post.get("alert_status")
    if state and state not in {"active", "scheduled"}:
        return False
    end = parse_timestamp(post.get("alert_valid_until"))
    return not end or end > (now or datetime.now(timezone.utc))
