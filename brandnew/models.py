"""The one record type every data source produces."""
from dataclasses import asdict, dataclass, field, fields
from datetime import date


@dataclass
class Release:
    kind: str                 # "books" or "music"
    id: str                   # ISBN-13 for books, MusicBrainz release-group ID for music
    title: str
    by: str                   # author(s) or artist
    date: date
    source: str               # e.g. "google-books", "listenbrainz"
    amazon_url: str           # built without contacting Amazon; the tag is added when rendering
    genres: list[str] = field(default_factory=list)   # our genre slugs
    tags: list[str] = field(default_factory=list)     # descriptive tags shown on the card
    cover: str | None = None
    cover_2x: str | None = None
    cover_backup: str | None = None  # albums: the Cover Art Archive link, when `cover` goes straight to the Internet Archive
    publisher: str = ""
    info_url: str | None = None  # the source's own page for this release (Google Books requires one)
    popularity: int = 0       # ListenBrainz listener count (music only)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Release":
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}  # data saved by older versions may have extra fields
        d["date"] = date.fromisoformat(d["date"])
        return cls(**d)
