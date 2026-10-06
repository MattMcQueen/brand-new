"""Sites built once and shared by every test that only reads them. Building takes about a second,
so most tests look at one of these instead of building their own. Tests that change the build's
inputs (their own releases, a different time, a patched config) still build into tmp_path."""
from datetime import date, datetime

import pytest

from brandnew import render, sample
from brandnew.ukdates import UK

TODAY = date(2026, 9, 25)
GENERATED = datetime(2026, 9, 25, 5, 31, tzinfo=UK)


def _build(factory, releases, amazon_tag=None):
    out = factory.mktemp("site")
    render.build(releases, GENERATED, out, TODAY, amazon_tag=amazon_tag)
    return out


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    """The sample data, with no Amazon tag."""
    return _build(tmp_path_factory, sample.releases(TODAY))


@pytest.fixture(scope="session")
def tagged_site(tmp_path_factory):
    """The sample data, with the Amazon tag test-21."""
    return _build(tmp_path_factory, sample.releases(TODAY), amazon_tag="test-21")


@pytest.fixture(scope="session")
def empty_site(tmp_path_factory):
    """No releases at all."""
    return _build(tmp_path_factory, [])
