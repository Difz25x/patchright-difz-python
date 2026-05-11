from __future__ import annotations

import asyncio
import time
import weakref
from typing import Any, Callable, Sequence

from patchright.async_api import _generated as async_generated
from patchright.sync_api import BrowserContext, ElementHandle, Locator, Page

from ._cloudflare_data import (
    CLOUDFLARE_DATA_SCRIPT,
    DEFAULT_TOKEN_MIN_LENGTH,
    CloudflareData,
    build_cloudflare_data,
    cloudflare_data_arg,
    empty_cloudflare_page_data,
    normalize_cookie_urls,
)
from ._turnstile_options import (
    DEFAULT_TURNSTILE_SELECTORS,
    FALLBACK_LIMIT,
    FALLBACK_SELECTORS,
    TurnstileOption,
    normalize_options,
)
from .turnstile_async import check_turnstile as _async_check_turnstile

_attached_pages: weakref.WeakSet[Page] = weakref.WeakSet()


def _box_value(box: Any, key: str) -> float:
    if isinstance(box, dict):
        return float(box[key])
    return float(getattr(box, key))


def _box_tuple(box: Any) -> tuple[float, float, float, float]:
    return (
        _box_value(box, "x"),
        _box_value(box, "y"),
        _box_value(box, "width"),
        _box_value(box, "height"),
    )


def _get_click_point(box: Any) -> tuple[float, float]:
    x, y, width, height = _box_tuple(box)
    x_offset = 30 if width > 80 else width / 2
    return x + x_offset, y + height / 2


def _click_box(page: Page, box: Any) -> bool:
    _x, _y, width, height = _box_tuple(box)
    if width <= 0 or height <= 0:
        return False

    x, y = _get_click_point(box)
    page.mouse.click(x, y)
    return True


def _looks_like_turnstile_box(box: Any) -> bool:
    _x, _y, width, height = _box_tuple(box)
    return 260 <= width <= 340 and 35 <= height <= 90


def _click_locator_box(page: Page, locator: Locator) -> bool:
    try:
        box = locator.bounding_box(timeout=1000)
    except Exception:
        return False

    if not box:
        return False

    return _click_box(page, box)


def _click_element_or_parent_box(page: Page, element: ElementHandle) -> bool:
    current: ElementHandle | None = element

    for _depth in range(8):
        if not current:
            break

        try:
            box = current.bounding_box()
        except Exception:
            box = None

        if box and _looks_like_turnstile_box(box) and _click_box(page, box):
            return True

        try:
            parent_handle = current.evaluate_handle(
                """(el) => {
                    const root = el.getRootNode();
                    if (el.parentElement) return el.parentElement;
                    if (root instanceof ShadowRoot) return root.host;
                    return null;
                }""",
                isolated_context=False,
            )
        except Exception:
            parent_handle = None

        current = parent_handle.as_element() if parent_handle else None

        if parent_handle and current is None:
            parent_handle.dispose()

    return False


def _click_turnstile_locators(
    page: Page,
    selectors: Sequence[str],
    max_candidates_per_selector: int,
) -> bool:
    for selector in selectors:
        locator = page.locator(selector)

        try:
            count = locator.count()
        except Exception:
            count = 0

        for index in range(min(count, max_candidates_per_selector)):
            target = locator.nth(index)

            if _click_locator_box(page, target):
                return True

            try:
                element = target.element_handle(timeout=1000)
            except Exception:
                element = None

            if not element:
                continue

            try:
                if _click_element_or_parent_box(page, element):
                    return True
            finally:
                element.dispose()

    return False


def _has_turnstile_locators(
    page: Page,
    selectors: Sequence[str],
    max_candidates_per_selector: int,
) -> bool:
    for selector in selectors:
        locator = page.locator(selector)

        try:
            count = locator.count()
        except Exception:
            count = 0

        for index in range(min(count, max_candidates_per_selector)):
            try:
                box = locator.nth(index).bounding_box(timeout=250)
            except Exception:
                box = None

            if box and _looks_like_turnstile_box(box):
                return True

        if count > 0:
            return True

    return False


def _has_turnstile_fallback(page: Page) -> bool:
    for selector in FALLBACK_SELECTORS:
        locator = page.locator(selector)

        try:
            count = min(locator.count(), FALLBACK_LIMIT)
        except Exception:
            count = 0

        for index in range(count):
            try:
                box = locator.nth(index).bounding_box(timeout=250)
            except Exception:
                box = None

            if box and _looks_like_turnstile_box(box):
                return True

    return False


def _click_turnstile_fallback(page: Page) -> bool:
    candidates: list[Any] = []

    for selector in FALLBACK_SELECTORS:
        locator = page.locator(selector)

        try:
            count = min(locator.count(), FALLBACK_LIMIT)
        except Exception:
            count = 0

        for index in range(count):
            try:
                box = locator.nth(index).bounding_box(timeout=250)
            except Exception:
                box = None

            if box and _looks_like_turnstile_box(box):
                candidates.append(box)

    def score(box: Any) -> float:
        _x, _y, width, height = _box_tuple(box)
        return abs(width - 300) + abs(height - 65)

    candidates.sort(key=score)

    for box in candidates:
        try:
            if _click_box(page, box):
                return True
        except Exception:
            pass

    return False


def _get_cloudflare_page_data(
    page: Page,
    *,
    min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH,
) -> CloudflareData:
    return page.evaluate(
        CLOUDFLARE_DATA_SCRIPT,
        cloudflare_data_arg(min_token_length),
    )


def has_turnstile(
    page: Page,
    *,
    selectors: Sequence[str] | None = None,
    max_candidates_per_selector: int = 5,
    include_fallback: bool = True,
) -> bool:
    selector_list = selectors or DEFAULT_TURNSTILE_SELECTORS

    if _has_turnstile_locators(
        page,
        selector_list,
        max_candidates_per_selector,
    ):
        return True

    if not include_fallback:
        return False

    return _has_turnstile_fallback(page)


def is_turnstile_solved(
    page: Page,
    *,
    min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH,
) -> bool:
    data = _get_cloudflare_page_data(page, min_token_length=min_token_length)

    return any(
        len(str(response.get("value", "")).strip()) >= min_token_length
        for response in data["turnstile"]["responses"]
    )


def get_cloudflare_data(
    page: Page | None = None,
    *,
    context: BrowserContext | None = None,
    urls: str | Sequence[str] | None = None,
) -> CloudflareData:
    context = context or (page.context if page else None)
    page_data = (
        _get_cloudflare_page_data(page)
        if page
        else empty_cloudflare_page_data()
    )

    if not context:
        cookies: list[Any] = []
    else:
        cookie_urls = normalize_cookie_urls(urls)
        try:
            cookies = (
                context.cookies(cookie_urls)
                if cookie_urls is not None
                else context.cookies()
            )
        except Exception:
            cookies = []

    return build_cloudflare_data(page_data, cookies)


def check_turnstile(
    page: Page,
    *,
    timeout_ms: int = 5000,
    selectors: Sequence[str] | None = None,
    max_candidates_per_selector: int = 5,
) -> bool:
    started_at = time.monotonic()
    selector_list = selectors or DEFAULT_TURNSTILE_SELECTORS

    while (time.monotonic() - started_at) * 1000 < timeout_ms:
        try:
            if _click_turnstile_locators(
                page,
                selector_list,
                max_candidates_per_selector,
            ):
                return True

            if _click_turnstile_fallback(page):
                return True
        except Exception:
            pass

        try:
            page.wait_for_timeout(500)
        except Exception:
            time.sleep(0.5)

    return False


def install_turnstile_auto_solver(
    context: BrowserContext,
    option: TurnstileOption = True,
) -> Callable[[], None]:
    options = normalize_options(option)
    page_cleanups: list[Callable[[], None]] = []
    loop = context._impl_obj._loop

    def attach_page(page: Page) -> None:
        if page in _attached_pages:
            return

        _attached_pages.add(page)
        async_page = async_generated.mapping.from_impl(page._impl_obj)
        closed = False
        running = False
        pending: set[asyncio.Task[Any]] = set()

        async def run() -> None:
            nonlocal running

            if closed or running:
                return

            running = True

            try:
                clicked = await _async_check_turnstile(
                    async_page,
                    timeout_ms=options.timeout_ms,
                    selectors=options.selectors,
                    max_candidates_per_selector=options.max_candidates_per_selector,
                )

                if clicked and options.logger:
                    options.logger("turnstile candidate clicked")
            except Exception as error:
                if options.logger:
                    options.logger(str(error))
            finally:
                running = False

        async def interval_loop() -> None:
            while not closed:
                await run()
                await asyncio.sleep(options.interval_ms / 1000)

        def track(task: asyncio.Task[Any]) -> None:
            pending.add(task)
            task.add_done_callback(pending.discard)

        def schedule(*_args: Any) -> None:
            if closed:
                return
            track(loop.create_task(run()))

        interval_task = loop.create_task(interval_loop())
        track(interval_task)

        def cleanup(*_args: Any) -> None:
            nonlocal closed

            if closed:
                return

            closed = True

            for event, handler in page_handlers:
                try:
                    page.remove_listener(event, handler)
                except Exception:
                    pass

            for task in list(pending):
                task.cancel()

        page_handlers = [
            ("close", cleanup),
            ("domcontentloaded", schedule),
            ("load", schedule),
            ("framenavigated", schedule),
        ]

        for event, handler in page_handlers:
            page.on(event, handler)

        page_cleanups.append(cleanup)
        schedule()

    for page in context.pages:
        attach_page(page)

    context.on("page", attach_page)

    def cleanup() -> None:
        try:
            context.remove_listener("page", attach_page)
        except Exception:
            pass

        for page_cleanup in list(page_cleanups):
            page_cleanup()

    return cleanup
