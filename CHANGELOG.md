# Changelog

## 0.4.1 - 2026-05-12

- Improved Turnstile clicking by bringing the page to the foreground before mouse actions and using stepped mouse movement.
- Reduced auto-solver polling latency and async fallback scan time.
- Made `cf-turnstile-response` a secondary signal instead of requiring it for active Turnstile detection.
- Allowed `is_turnstile_solved` to use `cf_clearance` cookie data when response fields are not present.

## 0.4.0 - 2026-05-12

- Added `has_turnstile` to detect whether a page currently contains Turnstile candidates.
- Added `is_turnstile_solved` to check for populated Turnstile response/token fields.
- Added `get_cloudflare_data` to collect Cloudflare cookies, clearance cookie,
  Turnstile responses/tokens, sitekeys, widget metadata, challenge fields,
  Ray IDs, and Cloudflare-related storage data.

## 0.3.0 - 2026-05-11

- Ported the npm package to Python packaging as `patchright-difz`.
- Added sync and async Patchright wrappers around `sync_playwright()` and
  `async_playwright()`.
- Defaulted evaluate helpers to the page main world while preserving
  `isolated_context=True` for explicit isolated-world calls.
- Added optional Turnstile candidate detection and clicking helpers.
- Added headless user-agent replacement before the first page request.
- Added a PyPI Trusted Publishing release workflow.
