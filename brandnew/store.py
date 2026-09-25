"""Reading and writing the releases data file (also published as /data/releases.json)."""
import json
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config
from .models import Release


def save(path: Path, releases: list[Release], generated: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"generated": generated.isoformat(timespec="seconds"),
            "releases": [r.to_dict() for r in releases]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def parse(data: dict) -> tuple[datetime, list[Release]]:
    return datetime.fromisoformat(data["generated"]), [Release.from_dict(r) for r in data["releases"]]


def load(path_or_url: str | Path) -> tuple[datetime, list[Release]]:
    """Load a data file from disk or from a URL (e.g. yesterday's published copy)."""
    s = str(path_or_url)
    if s.startswith(("http://", "https://")):
        req = urllib.request.Request(s, headers={"User-Agent": config.USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            return parse(json.load(r))
    return parse(json.loads(Path(s).read_text(encoding="utf-8")))
