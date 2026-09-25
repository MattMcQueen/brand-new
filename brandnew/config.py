"""Site settings and the genre lists."""
from dataclasses import dataclass, field

SITE_NAME = "Brand New"
SITE_URL = "https://brandnew.matt-rarely-writes.co.uk"
BLOG_URL = "https://www.matt-rarely-writes.co.uk"
KOFI_URL = "https://ko-fi.com/mattrarelywrites"
USER_AGENT = f"BrandNew/0.1 ( {SITE_URL} )"

AMAZON_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
AFFILIATE_REL = "sponsored nofollow noopener"

PAST_DAYS = 7            # "Out this week"
PAST_FALLBACK_DAYS = 14  # used when a genre has nothing in the last 7 days
UPCOMING_DAYS = 90       # "Coming soon"


@dataclass(frozen=True)
class Genre:
    slug: str
    name: str
    kind: str  # "books" or "music"
    # books: Google Books subject words; music: patterns matched against MusicBrainz genres/tags
    terms: tuple[str, ...] = field(default=())
    blurb: str = ""


BOOK_GENRES = (
    Genre("crime-thrillers", "Crime & thrillers", "books", ("thrillers", "crime"),
          "Detectives, heists, spies and page-turners."),
    Genre("sf-fantasy", "Science fiction & fantasy", "books", ("science fiction", "fantasy"),
          "Other worlds, futures and magic."),
    Genre("romance", "Romance", "books", ("romance",), "Love stories of every kind."),
    Genre("horror", "Horror", "books", ("horror",), "Ghosts, monsters and dread."),
    Genre("historical-fiction", "Historical fiction", "books", ("historical fiction",),
          "Stories set in the past."),
    Genre("literary-fiction", "Literary fiction", "books", ("literary fiction",),
          "Prize contenders and book-club picks."),
)

MUSIC_GENRES = (
    Genre("rock", "Rock", "music", ("rock",)),
    Genre("pop", "Pop", "music", ("pop",)),
    Genre("electronic", "Electronic", "music", ("electronic", "electronica", "techno", "idm", "drum and bass")),
    Genre("hip-hop", "Hip hop", "music", ("hip hop", "hip-hop", "rap")),
    Genre("folk", "Folk", "music", ("folk",)),
    Genre("jazz", "Jazz", "music", ("jazz",)),
    Genre("metal", "Metal", "music", ("metal",)),
    Genre("indie", "Indie", "music", ("indie",)),
)

ALL_GENRES = BOOK_GENRES + MUSIC_GENRES
KIND_NAMES = {"books": "Books", "music": "Music"}


def genres_of(kind: str) -> tuple[Genre, ...]:
    return BOOK_GENRES if kind == "books" else MUSIC_GENRES
