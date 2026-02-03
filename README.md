# statsscraper

Logs the public visitor counter from an event page to CSV every 10 minutes and renders an interactive chart on GitHub Pages.

## Quick start

```bash
python -m pip install -r requirements.txt
python scrape.py  # defaults to the current event URL
```

The output CSV is appended to `data/visitor_counter.csv` with UTC timestamps.

## Configuration

You can override defaults via CLI or environment variables:

```bash
python scrape.py --url https://example.com/event --out data/custom.csv --retries 5 --backoff 2.0 --verbose
```

Environment variables (highest precedence after CLI):

- `SCRAPER_URL`
- `SCRAPER_OUT_CSV`
- `SCRAPER_USER_AGENT`
- `SCRAPER_CONNECT_TIMEOUT`
- `SCRAPER_READ_TIMEOUT`
- `SCRAPER_RETRIES`
- `SCRAPER_BACKOFF`

Defaults live in `scrape.py` and remain backward-compatible; running with no args behaves like before.

## Logging

Structured logs go to stdout with UTC timestamps. Use `--verbose` for debug-level details. Failures surface as non-zero exit codes for GitHub Actions.

## GitHub Actions

- `.github/workflows/scrape.yml` runs every 10 minutes and commits the updated CSV.
- Concurrency is enabled to avoid overlapping runs; pushes rebase before committing.
- You can set `SCRAPER_URL` as a repository secret to point to a different page.

## GitHub Pages (interactive chart)

- The static site lives in `docs/` and deploys via `.github/workflows/pages.yml` to GitHub Pages (source: `main`).
- The chart fetches `data/visitor_counter.csv` from the repository, auto-refreshes, shades nights in light gray, and shows both raw and bot-corrected series (corrected subtracts one bot hit per logged row).
- Styling is minimal, modern, and responsive; built with Chart.js + annotation plugin.

## Data schema

`data/visitor_counter.csv`

| timestamp_utc | value | url |
| --- | --- | --- |
| ISO-8601 UTC | integer or blank | source URL |

## Notes

- Timestamps are stored in UTC.
- If the counter element disappears or can’t be parsed, the CSV logs `value` as blank; the scraper exits with error to signal the workflow.
- Night shading uses 21:00–07:00 (UTC-based) by default; adjust in `docs/index.html` if desired.
