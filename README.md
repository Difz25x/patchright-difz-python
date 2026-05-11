# patchright-difz

Patchright Python wrapper with an optional Turnstile helper.

## Install

```bash
pip install patchright-difz
```

## Sync usage

```py
from patchright_difz.sync_api import sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        ".profile",
        headless=False,
        channel="chrome",
        no_viewport=True,
        turnstile=True,
    )
    page = context.new_page()
    page.goto("https://example.com")
```

## Async usage

```py
from patchright_difz.async_api import async_playwright

async with async_playwright() as p:
    context = await p.chromium.launch_persistent_context(
        ".profile",
        headless=False,
        channel="chrome",
        no_viewport=True,
        turnstile=True,
    )
    page = await context.new_page()
    await page.goto("https://example.com")
```

`page.evaluate`, `frame.evaluate`, locator evaluate helpers, and handle
evaluate helpers default to the page main world in this wrapper. If you need
Patchright's isolated world for a specific call, pass `isolated_context=True`.

The Turnstile helper uses Patchright locators for fallback detection, so it can
also pick up challenge candidates rendered inside closed shadow roots.
The hidden `cf-turnstile-response` field is only used as optional token/data
evidence; active challenge detection prefers visible widgets, iframes, and
clickable candidates.

When `headless=True` is used without a custom `user_agent`, the wrapper sets a
normal Chrome user agent before the first request. This applies to
`launch_persistent_context`, `browser.new_context`, and `browser.new_page`.
Set `PATCHRIGHT_DIFZ_HEADLESS_USER_AGENT=0` to keep Patchright's default
headless user agent, or set it to a full user-agent string to override the
default.

## Configure Turnstile

```py
context = p.chromium.launch_persistent_context(
    ".profile",
    headless=False,
    channel="chrome",
    no_viewport=True,
    turnstile={
        "timeout_ms": 5000,
        "interval_ms": 750,
        "foreground": True,
        "click_delay_ms": 35,
        "mouse_move_steps": 8,
        "logger": print,
    },
)
```

Camel-case option names from the npm package are also accepted:
`timeoutMs`, `intervalMs`, `maxCandidatesPerSelector`, `clickDelayMs`,
`mouseMoveSteps`, and `waitAfterClickMs`.

## Manual usage

```py
from patchright_difz.sync_api import check_turnstile, sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        ".profile",
        headless=False,
        channel="chrome",
        no_viewport=True,
    )
    page = context.new_page()
    page.goto("https://example.com")
    check_turnstile(page)
```

## Turnstile and Cloudflare data helpers

```py
from patchright_difz.sync_api import (
    get_cloudflare_data,
    has_turnstile,
    is_turnstile_solved,
)

exists = has_turnstile(page)
solved = is_turnstile_solved(page)
data = get_cloudflare_data(page)

print({
    "exists": exists,
    "solved": solved,
    "cookies": data["cloudflare_cookies"],
    "clearance": data["clearance_cookie"],
    "cleared": data["challenge"]["cleared"],
    "document_cookie_names": data["document_cookie_names"],
    "tokens": data["turnstile"]["tokens"],
    "sitekeys": data["turnstile"]["sitekeys"],
    "responses": data["turnstile"]["responses"],
})
```

Async usage uses the same names with `await`:

```py
from patchright_difz.async_api import get_cloudflare_data

data = await get_cloudflare_data(page)
```

`get_cloudflare_data` reads the current browser context cookies plus visible
page data such as Turnstile response fields, widget `sitekey` values,
Cloudflare iframe/script URLs, challenge fields, Ray IDs, and
Cloudflare-related local/session storage keys. Pass `context` and `urls` when
you only want cookie data for specific URLs:

```py
data = get_cloudflare_data(
    context=context,
    urls=["https://example.com"],
)
```

## Publish

```bash
python scripts/publish.py
```

The command builds, creates a `v<version>` git tag, pushes to GitHub, and lets
the GitHub Actions workflow publish to PyPI through Trusted Publishing.
