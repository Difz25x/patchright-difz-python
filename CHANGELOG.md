# Changelog

## 0.3.0 - 2026-05-11

- Ported the npm package to Python packaging as `patchright-difz`.
- Added sync and async Patchright wrappers around `sync_playwright()` and
  `async_playwright()`.
- Defaulted evaluate helpers to the page main world while preserving
  `isolated_context=True` for explicit isolated-world calls.
- Added optional Turnstile candidate detection and clicking helpers.
- Added headless user-agent replacement before the first page request.
- Added a PyPI Trusted Publishing release workflow.
