"""Runs the data sources and guards against bad days: if a source fails or comes back
suspiciously small, yesterday's releases for it (or for an emptied genre) are kept."""
import sys
from collections.abc import Callable
from datetime import date

from . import config
from .models import Release
from .ukdates import in_fetch_window

SHRINK_LIMIT = 0.3  # a source returning under 30% of yesterday's count is treated as broken


def _count(releases: list[Release], slug: str) -> int:
    return sum(slug in r.genres for r in releases)


def with_fallback(kind: str, fetch: Callable[[], list[Release]], previous: list[Release],
                  today: date) -> list[Release]:
    prev = [r for r in previous if r.kind == kind and in_fetch_window(r.date, today)]
    try:
        fresh = fetch()
    except Exception as e:  # noqa: BLE001 - any failure means "use yesterday's data"
        print(f"! {kind}: source failed ({e}); keeping {len(prev)} releases from the previous run", file=sys.stderr)
        return prev
    if prev and len(fresh) < SHRINK_LIMIT * len(prev):
        print(f"! {kind}: only {len(fresh)} releases against {len(prev)} last time; keeping the previous run",
              file=sys.stderr)
        return prev
    have = {r.id for r in fresh}
    for g in config.genres_of(kind):
        if _count(fresh, g.slug) == 0 and _count(prev, g.slug) > 0:
            carried = [r for r in prev if g.slug in r.genres and r.id not in have]
            print(f"! {kind}/{g.slug}: nothing today; keeping {len(carried)} from the previous run", file=sys.stderr)
            fresh += carried
            have.update(r.id for r in carried)
    return fresh
