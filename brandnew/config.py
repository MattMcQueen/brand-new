"""Site settings and the genre lists."""
from dataclasses import dataclass, field

SITE_NAME = "Brand New"
SITE_URL = "https://brand-new.matt-rarely-writes.co.uk"
BLOG_URL = "https://www.matt-rarely-writes.co.uk"
KOFI_URL = "https://ko-fi.com/mattrarelywrites"
USER_AGENT = f"BrandNew/0.1 ( {SITE_URL} )"

# Cloudflare Web Analytics site token (public: it's in every page). Empty = no analytics script.
CLOUDFLARE_ANALYTICS_TOKEN = "b54662e6c057425781fbab2cdcd31e9a"

AMAZON_TAG = "matsbasblo-21"  # Associates UK tracking ID (public: it's in every link). AMAZON_TAG env var overrides.
AMAZON_DISCLOSURE ="As an Amazon Associate I earn from qualifying purchases."
AFFILIATE_REL = "sponsored nofollow noopener"
OTHER_SHOP_REL = "nofollow noopener"  # other bookshops: not affiliate links

PAST_DAYS = 7            # "Out this week"
PAST_FALLBACK_DAYS = 14  # used when a genre has nothing in the last 7 days
STALE_HOURS = 48         # older data than this shows a "running late" notice (see static/app.js)
UPCOMING_DAYS = 90       # "Coming soon"


@dataclass(frozen=True)
class Genre:
    slug: str
    name: str
    kind: str  # "books" or "music"
    # books: Google Books subject headings, e.g. "fiction / horror"; music: patterns matched against
    # MusicBrainz genres/tags
    terms: tuple[str, ...] = field(default=())
    blurb: str = ""


# Most popular first (UK sales, Nielsen BookScan 2025): the order of tiles, chips and fetching.
BOOK_GENRES = (
    Genre("crime-thrillers", "Crime & thrillers", "books",
          ("fiction / thrillers", "fiction / mystery & detective", "fiction / crime"),
          "Detectives, heists, spies and page-turners."),
    Genre("childrens", "Children's", "books", ("juvenile fiction",),
          "Picture books, first chapter books and middle-grade adventures."),
    Genre("romance", "Romance", "books", ("fiction / romance",), "Love stories of every kind."),
    Genre("fantasy", "Fantasy", "books", ("fiction / fantasy",), "Magic, quests and other worlds."),
    Genre("literary-fiction", "Literary fiction", "books", ("fiction / literary",),
          "Prize contenders and book-club picks."),
    Genre("historical-fiction", "Historical fiction", "books", ("fiction / historical",),
          "Stories set in the past."),
    Genre("science-fiction", "Science fiction", "books", ("fiction / science fiction",),
          "Space, the future, and science that changes everything."),
    Genre("horror", "Horror", "books", ("fiction / horror",), "Ghosts, monsters and dread."),
)

# Most popular first (UK album market share, BPI 2025; it counts indie and metal within rock and pop).
MUSIC_GENRES = (
    Genre("rock", "Rock", "music", ("rock",)),
    Genre("pop", "Pop", "music", ("pop",)),
    Genre("hip-hop", "Hip hop", "music", ("hip hop", "hip-hop", "rap")),
    Genre("rnb-soul", "R&B & soul", "music", ("r&b", "rnb", "soul")),
    Genre("electronic", "Electronic", "music", ("electronic", "electronica", "techno", "idm", "drum and bass")),
    Genre("indie", "Indie", "music", ("indie",)),
    Genre("metal", "Metal", "music", ("metal", "metalcore")),
    Genre("country", "Country", "music", ("country", "americana", "bluegrass")),
    Genre("folk", "Folk", "music", ("folk",)),
    Genre("jazz", "Jazz", "music", ("jazz",)),
)

ALL_GENRES = BOOK_GENRES + MUSIC_GENRES
KIND_NAMES = {"books": "Books", "music": "Music"}


def genres_of(kind: str) -> tuple[Genre, ...]:
    return BOOK_GENRES if kind == "books" else MUSIC_GENRES
