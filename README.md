# Brand New

New and upcoming book and music releases by genre, with links to Amazon UK.
To be hosted at https://brandnew.matt-rarely-writes.co.uk.

Status: in development. Nothing is deployed yet.

## How it works

A Python script fetches releases, renders plain HTML pages into `dist/`, and (later) a scheduled
GitHub Action rebuilds it every morning and deploys it to Azure Static Web Apps.

## Local development

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m brandnew build --sample     # made-up data
.venv/Scripts/python -m brandnew serve              # http://localhost:8000
.venv/Scripts/python -m pytest
```

Set `AMAZON_TAG` to add the Associates tracking tag to Amazon links.

## Data sources

- Music: [ListenBrainz](https://listenbrainz.org) and [MusicBrainz](https://musicbrainz.org) (CC0),
  covers from the [Cover Art Archive](https://coverartarchive.org).
- Books: [Google Books API](https://developers.google.com/books).

As an Amazon Associate I earn from qualifying purchases.
