# Brand New

New and upcoming book and music releases by genre, with links to Amazon UK and other shops.
Live at https://brand-new.matt-rarely-writes.co.uk.

## How it works

A Python script fetches releases and renders plain HTML pages into `dist/`. The
[Build site](.github/workflows/build.yml) GitHub Action runs the tests on every pull request and
rebuilds the site with fresh data once a day and whenever `main` changes. The daily run has three
scheduled slots, 09:17, 11:47 and 15:17 UK time in summer (an hour earlier in winter), because
GitHub's schedules are best-effort; a slot stops early when the live site already has today's data.
Each run's data and MusicBrainz genre lookups are kept in the Actions cache for the next run. The
built site is attached to each run for a week, and runs on `main` deploy it to Azure Static Web Apps
(only while the repository variable `DEPLOY_ENABLED` is `true`).

Secrets (GitHub Actions): `GOOGLE_BOOKS_KEY`, `AZURE_STATIC_WEB_APPS_API_TOKEN`.

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

### In Docker

Serves whatever is in `dist/` at http://localhost:8080 (this computer only). Build the site first;
`build` with no `--data` uses `.cache/releases.json`, the last fetched data, so it makes no API calls.

```bash
.venv/Scripts/python -m brandnew build
docker compose up -d      # start
docker compose down       # stop and remove
```

After rebuilding, just refresh the page: `dist/` is mounted, not copied.

The Docker preview doesn't send the live site's security headers. `brandnew serve` (port 8000) does:
it applies the headers and 404 page from `dist/staticwebapp.config.json`, which `build` writes from
`brandnew/hosting.py`, so it's the one to use when checking anything the Content Security Policy
might block.

## Data sources

- Music: [ListenBrainz](https://listenbrainz.org) and [MusicBrainz](https://musicbrainz.org) (CC0),
  covers from the [Cover Art Archive](https://coverartarchive.org).
- Books: [Google Books API](https://developers.google.com/books).

As an Amazon Associate I earn from qualifying purchases.
