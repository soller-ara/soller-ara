#!/usr/bin/env python3
"""Recheck a watchdog request AFTER acquiring the existing workflow lock."""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def should_collect(payload: dict, now: datetime) -> bool:
    value = payload.get('sources_checked_at')
    if not isinstance(value, str):
        raise ValueError('No hay una fecha verificable de revisión de fuentes')
    try:
        checked = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('La fecha de revisión no es válida') from error
    if checked.tzinfo is None or checked > now + timedelta(minutes=5):
        raise ValueError('La fecha de revisión no es válida')
    return now - checked > timedelta(hours=2)


def main() -> None:
    payload = json.loads((ROOT / 'data/posts.json').read_text(encoding='utf-8'))
    collect = should_collect(payload, datetime.now(timezone.utc))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('collect=' + str(collect).lower() + '\n')
    print('WATCHDOG_GUARD: ' + ('revisión atrasada; continuar' if collect else 'revisión reciente; no repetir'))


if __name__ == '__main__':
    main()
