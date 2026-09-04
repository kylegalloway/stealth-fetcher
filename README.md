# stealth-fetcher

A reusable tool for fetching pages that sit behind a Cloudflare (or similar)
JS challenge, where a plain `requests`/`curl` call gets a 403. Built after
`fbschedules.com` (the primary source for
[`cfb-tv-schedule`](../cfb-tv-schedule)) turned on Cloudflare's managed
challenge and started blocking that scraper's HTTP client.

**This project only knows how to drive a browser that can pass the
challenge — it has no opinion on which site or which pages.** That knowledge
(URLs, selectors, how to parse and save the result) belongs in whichever
project actually needs the data — see "Using it from another project" below.

Two interchangeable browser engines, both driven through Playwright's API:

- **camoufox** (default) — a hardened Firefox build that patches the
  fingerprinting signals (canvas/WebGL noise, navigator properties, timing)
  Cloudflare's challenge checks.
- **chrome** — [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright),
  a patched Chromium/Playwright build that removes the CDP-detectable traces
  stock Playwright/Selenium leave behind.

Neither is guaranteed to keep working forever — Cloudflare updates its
detection over time — but both aim to pass a JS challenge that a plain HTTP
client cannot.

## Setup

Uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync

# download the actual browser binaries (one-time, per engine you use)
uv run camoufox fetch
uv run patchright install chromium
```

## Usage

### Ad-hoc fetch

```bash
# rendered HTML to stdout
uv run stealth-fetcher fetch https://example.com

# save to a file, using the chrome (patchright) engine, watch the browser,
# and wait for a specific element instead of network-idle (challenge pages
# can look "idle" before they've actually resolved)
uv run stealth-fetcher --engine chrome --headed fetch https://example.com \
    -o page.html --wait-for "#main-content"
```

### Using it from another project

Any project can define its own fetch script and hand it to stealth-fetcher's
`run` command. The script must define:

```python
def run(session, argv: list[str]) -> None:
    ...
```

`session` is a `BrowserSession` (see `stealth_fetcher/engines.py`) that has
already loaded past whatever challenge the target site throws up:

- `session.goto(url, wait_selector=None, timeout_ms=30_000) -> str` —
  navigates and returns the rendered HTML. Pass `wait_selector` for a page
  whose content loads after the challenge resolves (recommended — networkidle
  can fire on the challenge page itself before it redirects).
- `session.get(url, params=None) -> str` — makes a request in the same
  browser context (so it carries the cookies picked up while passing the
  challenge), e.g. for hitting a site's AJAX/API endpoints directly instead
  of navigating a full page per request.

`argv` is whatever args follow `--` on the command line, so the script can
take its own options (output path, etc.) via its own `argparse`.

```bash
uv run stealth-fetcher run /path/to/some_project/fetch_thing.py -- -o ./out
uv run stealth-fetcher --engine chrome run /path/to/fetch_thing.py -- --some-flag
```

See [`cfb-tv-schedule/fetch_fbschedules.py`](../cfb-tv-schedule/fetch_fbschedules.py)
for a real example — it fetches fbschedules.com's week list and every week's
AJAX schedule fragment, writing files `cfb-tv-schedule`'s own scraper knows
how to import.

## Notes

- `run` loads the script by file path via `importlib` — it does not need to
  be installed as a package, and it runs in stealth-fetcher's own venv (so it
  can rely on stealth-fetcher's dependencies, like `beautifulsoup4`, being
  present; add more to stealth-fetcher's `pyproject.toml` if a script needs
  them).
- If a site's challenge starts blocking one engine, try `--engine chrome` (or
  vice versa) before assuming the site added something new.
