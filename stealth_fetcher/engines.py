"""Browser engines that can pass a Cloudflare JS challenge, unlike a plain
`requests` call.

Two backends, both driven through Playwright's API:

- camoufox: a hardened Firefox build that patches the fingerprinting
  signals (canvas/WebGL noise, navigator properties, timing) that
  Cloudflare's managed challenge checks.
- patchright: a patched build of Chromium/Playwright that removes the
  CDP-detectable traces stock Playwright/Selenium leave behind.

Both expose the same small `BrowserSession` interface: `goto()` to load a
page (returns the rendered HTML after any challenge resolves) and `get()` to
make a follow-up request (e.g. an AJAX call) that behaves like the page
making it — i.e. via `fetch()` run *inside* the loaded page, not a
side-channel HTTP client. That matters: Playwright's `context.request` API
carries cookies but not the rest of what identifies a real page-driven
request (TLS/JA3 fingerprint, sec-fetch-* headers, same-origin framing), and
Cloudflare's WAF has been observed rejecting it with a 403 even once the
page itself has passed the challenge and holds a valid cf_clearance cookie.
Running `fetch()` in-page avoids that gap entirely.
"""

from __future__ import annotations

import base64
from typing import Protocol
from urllib.parse import urlencode


class BrowserSession(Protocol):
    def goto(self, url: str, wait_selector: str | None = None, timeout_ms: int = 30_000) -> str: ...

    def get(self, url: str, params: dict[str, str] | None = None) -> str: ...

    def get_binary(self, url: str) -> bytes: ...


class _PlaywrightSession:
    """Shared implementation for any Playwright-API-compatible browser
    (camoufox and patchright both speak this API)."""

    def __init__(self, page):
        self._page = page

    def goto(self, url: str, wait_selector: str | None = None, timeout_ms: int = 30_000) -> str:
        self._page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        if wait_selector:
            self._page.wait_for_selector(wait_selector, timeout=timeout_ms)
        else:
            self._page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return self._page.content()

    def get(self, url: str, params: dict[str, str] | None = None) -> str:
        full_url = f"{url}?{urlencode(params)}" if params else url
        return self._page.evaluate(
            """async (url) => {
                const resp = await fetch(url, {credentials: 'include'});
                if (!resp.ok) {
                    throw new Error(`GET ${url} -> ${resp.status} ${resp.statusText}`);
                }
                return await resp.text();
            }""",
            full_url,
        )

    def get_binary(self, url: str) -> bytes:
        """Like get(), but for binary responses (images, etc.) — same
        in-page fetch() so it carries the challenge-passing session, base64
        round-tripped through page.evaluate() since that channel is text-only.
        Goes via Blob/FileReader rather than iterating the raw ArrayBuffer
        bytes — camoufox (Firefox) raises "Accessing TypedArray data over
        Xrays is slow, and forbidden" if content-script code touches a
        TypedArray's bytes directly; FileReader stays entirely in-page."""
        data_url = self._page.evaluate(
            """async (url) => {
                const resp = await fetch(url, {credentials: 'include'});
                if (!resp.ok) {
                    throw new Error(`GET ${url} -> ${resp.status} ${resp.statusText}`);
                }
                const blob = await resp.blob();
                return await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = () => reject(reader.error);
                    reader.readAsDataURL(blob);
                });
            }""",
            url,
        )
        b64 = data_url.split(",", 1)[1]
        return base64.b64decode(b64)


class camoufox_session:
    """Context manager: `with camoufox_session() as session: ...`"""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._cm = None
        self._browser = None
        self._context = None

    def __enter__(self) -> _PlaywrightSession:
        from camoufox.sync_api import Camoufox

        self._cm = Camoufox(headless=self._headless, geoip=True)
        self._browser = self._cm.__enter__()
        self._context = self._browser.new_context()
        page = self._context.new_page()
        return _PlaywrightSession(page)

    def __exit__(self, *exc):
        if self._context is not None:
            self._context.close()
        if self._cm is not None:
            self._cm.__exit__(*exc)


class patchright_session:
    """Context manager: `with patchright_session() as session: ...`"""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._pw_cm = None
        self._browser = None
        self._context = None

    def __enter__(self) -> _PlaywrightSession:
        from patchright.sync_api import sync_playwright

        self._pw_cm = sync_playwright()
        pw = self._pw_cm.__enter__()
        self._browser = pw.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context()
        page = self._context.new_page()
        return _PlaywrightSession(page)

    def __exit__(self, *exc):
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._pw_cm is not None:
            self._pw_cm.__exit__(*exc)


ENGINES = {
    "camoufox": camoufox_session,
    "chrome": patchright_session,
}
