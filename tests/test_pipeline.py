from datetime import date, timedelta

import pytest

from brandnew import pipeline
from brandnew.models import Release

TODAY = date(2026, 9, 25)


def rel(id_, genre="rock", days=0):
    return Release(kind="music", id=id_, title=id_, by="B", date=TODAY + timedelta(days=days),
                   source="t", amazon_url="u", genres=[genre])


PREVIOUS = [rel(f"p{i}") for i in range(10)] + [rel("pj", "jazz"), rel("gone", days=-30)]


def test_source_failure_keeps_previous_in_window():
    def boom():
        raise RuntimeError("down")
    out = pipeline.with_fallback("music", boom, PREVIOUS, TODAY)
    assert len(out) == 11 and all(r.id != "gone" for r in out)


def test_big_shrink_keeps_previous():
    out = pipeline.with_fallback("music", lambda: [rel("new")], PREVIOUS, TODAY)
    assert len(out) == 11


def test_empty_genre_is_carried_over():
    fresh = [rel(f"n{i}") for i in range(8)]
    out = pipeline.with_fallback("music", lambda: fresh, PREVIOUS, TODAY)
    assert {r.id for r in out} == {f"n{i}" for i in range(8)} | {"pj"}


@pytest.mark.parametrize("previous", [[], PREVIOUS])
def test_normal_day_uses_fresh(previous):
    fresh = [rel(f"n{i}") for i in range(10)] + [rel("nj", "jazz")]
    assert pipeline.with_fallback("music", lambda: fresh, previous, TODAY) == fresh


def test_old_data_with_removed_fields_still_loads():
    from brandnew.models import Release
    r = Release.from_dict({"kind": "books", "id": "1", "title": "T", "by": "B", "date": "2026-09-25",
                           "source": "google-books", "amazon_url": "u", "note": ""})
    assert r.title == "T" and not r.uk_edition
