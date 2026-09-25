# Brand New

New and upcoming book and music releases by genre, with links to Amazon UK.
To be hosted at https://brandnew.matt-rarely-writes.co.uk.

Status: in development. Nothing is deployed yet.

## How it works

A Python script fetches releases, renders plain HTML pages into `dist/`, and (later) a scheduled
GitHub Action rebuilds it every morning and deploys it to Azure Static Web Apps.

## Picks of the week

Edit [`picks.yaml`](picks.yaml) (instructions are at the top of the file) and commit to `main`.
Picks show at the top of the home page with your note, and get a badge in their genre list.

## Local development

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m brandnew build --sample     # made-up data
.venv/Scripts/python -m brandnew serve              # http://localhost:8000
.venv/Scripts/python -m pytest
```

Real data (`fetch` writes `.cache/releases.json`, which `build` then uses):

```bash
GOOGLE_BOOKS_KEY_FILE=path/to/key.txt .venv/Scripts/python -m brandnew fetch
.venv/Scripts/python -m brandnew build
```

- `GOOGLE_BOOKS_KEY` (or `GOOGLE_BOOKS_KEY_FILE`, a file containing it): Google Books API key. Never commit it.
- `AMAZON_TAG`: overrides the Associates tracking tag in `brandnew/config.py` (matsbasblo-21).
- The first music fetch takes about 10 minutes (MusicBrainz allows 1 request a second); artist genres are then cached in `.cache/`.

## Data sources

- Music: [ListenBrainz](https://listenbrainz.org) and [MusicBrainz](https://musicbrainz.org) (CC0),
  covers from the [Cover Art Archive](https://coverartarchive.org).
- Books: [Google Books API](https://developers.google.com/books).

As an Amazon Associate I earn from qualifying purchases.
