# Brand New

New and upcoming book and music releases by genre, with links to Amazon UK.
To be hosted at https://brandnew.matt-rarely-writes.co.uk.

Status: in development. Nothing is deployed yet.

## How it works

A Python script fetches releases and renders plain HTML pages into `dist/`. The
[Build site](.github/workflows/build.yml) GitHub Action runs the tests on every pull request and
rebuilds the site every morning (about 05:17 UK time in summer, 04:17 in winter) and whenever `main`
changes. Each run's data and MusicBrainz genre lookups are kept in the Actions cache for the next run.
The built site is attached to each run for a week. Deploying to Azure Static Web Apps is off until the
repository variable `DEPLOY_ENABLED` is `true` and the `AZURE_STATIC_WEB_APPS_API_TOKEN` secret exists.

Secrets: `GOOGLE_BOOKS_KEY` (GitHub Actions secret).

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
