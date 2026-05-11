from __future__ import annotations

import asyncio
import inspect
import weakref
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from patchright.async_api import BrowserContext, ElementHandle, Locator, Page

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
    OPTIONAL_TURNSTILE_RESPONSE_SELECTORS,
    TurnstileAutoOptions,
    TurnstileOption,
    normalize_options,
)

_attached_pages: weakref.WeakSet[Page] = weakref.WeakSet()


@dataclass(frozen=True)
class ClickBehaviorOptions:
    foreground: bool = True
    click_delay_ms: int = 35
    mouse_move_steps: int = 8
    wait_after_click_ms: int = 150


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


async def _prepare_page_for_click(
    page: Page,
    options: ClickBehaviorOptions,
) -> None:
    if not options.foreground:
        return

    try:
        await page.bring_to_front()
    except Exception:
        pass

    try:
        await page.evaluate(
            "() => { window.focus(); document.body?.focus?.(); }",
            isolated_context=False,
        )
    except Exception:
        pass


async def _click_box(
    page: Page,
    box: Any,
    options: ClickBehaviorOptions,
) -> bool:
    _x, _y, width, height = _box_tuple(box)
    if width <= 0 or height <= 0:
        return False

    x, y = _get_click_point(box)
    await _prepare_page_for_click(page, options)
    await page.mouse.move(x, y, steps=options.mouse_move_steps)
    await page.mouse.down()

    if options.click_delay_ms > 0:
        try:
            await page.wait_for_timeout(options.click_delay_ms)
        except Exception:
            await asyncio.sleep(options.click_delay_ms / 1000)

    await page.mouse.up()

    if options.wait_after_click_ms > 0:
        try:
            await page.wait_for_timeout(options.wait_after_click_ms)
        except Exception:
            await asyncio.sleep(options.wait_after_click_ms / 1000)

    return True


def _looks_like_turnstile_box(box: Any) -> bool:
    _x, _y, width, height = _box_tuple(box)
    return 260 <= width <= 340 and 35 <= height <= 90


def _is_optional_response_selector(selector: str) -> bool:
    return selector in OPTIONAL_TURNSTILE_RESPONSE_SELECTORS


async def _click_locator_box(
    page: Page,
    locator: Locator,
    options: ClickBehaviorOptions,
) -> bool:
    try:
        box = await locator.bounding_box(timeout=1000)
    except Exception:
        return False

    if not box:
        return False

    x, y = _get_click_point(box)
    box_x, box_y, _width, _height = _box_tuple(box)
    await _prepare_page_for_click(page, options)

    try:
        await locator.click(
            force=True,
            timeout=1000,
            delay=options.click_delay_ms,
            steps=options.mouse_move_steps,
            position={
                "x": max(1, x - box_x),
                "y": max(1, y - box_y),
            },
        )

        if options.wait_after_click_ms > 0:
            await page.wait_for_timeout(options.wait_after_click_ms)

        return True
    except Exception:
        return await _click_box(page, box, options)


async def _click_element_or_parent_box(
    page: Page,
    element: ElementHandle,
    options: ClickBehaviorOptions,
) -> bool:
    current: ElementHandle | None = element

    for _depth in range(8):
        if not current:
            break

        try:
            box = await current.bounding_box()
        except Exception:
            box = None

        if box and _looks_like_turnstile_box(box) and await _click_box(page, box, options):
            return True

        try:
            parent_handle = await current.evaluate_handle(
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
            await parent_handle.dispose()

    return False


async def _click_turnstile_locators(
    page: Page,
    selectors: Sequence[str],
    max_candidates_per_selector: int,
    options: ClickBehaviorOptions,
) -> bool:
    for selector in selectors:
        locator = page.locator(selector)

        try:
            count = await locator.count()
        except Exception:
            count = 0

        for index in range(min(count, max_candidates_per_selector)):
            target = locator.nth(index)

            if await _click_locator_box(page, target, options):
                return True

            try:
                element = await target.element_handle(timeout=1000)
            except Exception:
                element = None

            if not element:
                continue

            try:
                if await _click_element_or_parent_box(page, element, options):
                    return True
            finally:
                await element.dispose()

    return False


async def _has_turnstile_locators(
    page: Page,
    selectors: Sequence[str],
    max_candidates_per_selector: int,
) -> bool:
    for selector in selectors:
        locator = page.locator(selector)

        try:
            count = await locator.count()
        except Exception:
            count = 0

        for index in range(min(count, max_candidates_per_selector)):
            try:
                box = await locator.nth(index).bounding_box(timeout=250)
            except Exception:
                box = None

            if box and _looks_like_turnstile_box(box):
                return True

        if count > 0 and not _is_optional_response_selector(selector):
            return True

    return False


async def _has_turnstile_fallback(page: Page) -> bool:
    for selector in FALLBACK_SELECTORS:
        locator = page.locator(selector)

        try:
            count = min(await locator.count(), FALLBACK_LIMIT)
        except Exception:
            count = 0

        boxes = await asyncio.gather(
            *(
                locator.nth(index).bounding_box(timeout=250)
                for index in range(count)
            ),
            return_exceptions=True,
        )

        if any(
            not isinstance(box, Exception) and box and _looks_like_turnstile_box(box)
            for box in boxes
        ):
            return True

    return False


async def _click_turnstile_fallback(
    page: Page,
    options: ClickBehaviorOptions,
) -> bool:
    candidates: list[Any] = []

    for selector in FALLBACK_SELECTORS:
        locator = page.locator(selector)

        try:
            count = min(await locator.count(), FALLBACK_LIMIT)
        except Exception:
            count = 0

        boxes = await asyncio.gather(
            *(
                locator.nth(index).bounding_box(timeout=250)
                for index in range(count)
            ),
            return_exceptions=True,
        )

        for box in boxes:
            if not isinstance(box, Exception) and box and _looks_like_turnstile_box(box):
                candidates.append(box)

    def score(box: Any) -> float:
        _x, _y, width, height = _box_tuple(box)
        return abs(width - 300) + abs(height - 65)

    candidates.sort(key=score)

    for box in candidates:
        try:
            if await _click_box(page, box, options):
                return True
        except Exception:
            pass

    return False


async def _get_cloudflare_page_data(
    page: Page,
    *,
    min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH,
) -> CloudflareData:
    return await page.evaluate(
        CLOUDFLARE_DATA_SCRIPT,
        cloudflare_data_arg(min_token_length),
    )


async def has_turnstile(
    page: Page,
    *,
    selectors: Sequence[str] | None = None,
    max_candidates_per_selector: int = 5,
    include_fallback: bool = True,
) -> bool:
    selector_list = selectors or DEFAULT_TURNSTILE_SELECTORS

    if await _has_turnstile_locators(
        page,
        selector_list,
        max_candidates_per_selector,
    ):
        return True

    if not include_fallback:
        return False

    return await _has_turnstile_fallback(page)


async def is_turnstile_solved(
    page: Page | None = None,
    *,
    context: BrowserContext | None = None,
    urls: str | Sequence[str] | None = None,
    min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH,
) -> bool:
    data = await get_cloudflare_data(
        page,
        context=context,
        urls=urls,
        min_token_length=min_token_length,
    )

    return bool(data["clearance_cookie"]) or any(
        len(str(token).strip()) >= min_token_length
        for token in data["turnstile"]["tokens"]
    )


async def get_cloudflare_data(
    page: Page | None = None,
    *,
    context: BrowserContext | None = None,
    urls: str | Sequence[str] | None = None,
    min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH,
) -> CloudflareData:
    context = context or (page.context if page else None)
    page_data = (
        await _get_cloudflare_page_data(page, min_token_length=min_token_length)
        if page
        else empty_cloudflare_page_data()
    )

    if not context:
        cookies: list[Any] = []
    else:
        cookie_urls = normalize_cookie_urls(urls)
        try:
            cookies = (
                await context.cookies(cookie_urls)
                if cookie_urls is not None
                else await context.cookies()
            )
        except Exception:
            cookies = []

    return build_cloudflare_data(page_data, cookies)


async def check_turnstile(
    page: Page,
    *,
    timeout_ms: int = 5000,
    selectors: Sequence[str] | None = None,
    max_candidates_per_selector: int = 5,
    foreground: bool = True,
    click_delay_ms: int = 35,
    mouse_move_steps: int = 8,
    wait_after_click_ms: int = 150,
) -> bool:
    started_at = asyncio.get_running_loop().time()
    selector_list = selectors or DEFAULT_TURNSTILE_SELECTORS
    click_options = ClickBehaviorOptions(
        foreground=foreground,
        click_delay_ms=click_delay_ms,
        mouse_move_steps=mouse_move_steps,
        wait_after_click_ms=wait_after_click_ms,
    )

    try:
        if await is_turnstile_solved(page):
            return True
    except Exception:
        pass

    while (asyncio.get_running_loop().time() - started_at) * 1000 < timeout_ms:
        try:
            if await _click_turnstile_locators(
                page,
                selector_list,
                max_candidates_per_selector,
                click_options,
            ):
                return True

            if await _click_turnstile_fallback(page, click_options):
                return True
        except Exception:
            pass

        try:
            await page.wait_for_timeout(250)
        except Exception:
            await asyncio.sleep(0.25)

    return False


def install_turnstile_auto_solver(
    context: BrowserContext,
    option: TurnstileOption = True,
) -> Callable[[], None]:
    options = normalize_options(option)
    page_cleanups: list[Callable[[], None]] = []

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    def attach_page(page: Page) -> None:
        if page in _attached_pages:
            return

        _attached_pages.add(page)
        closed = False
        running = False
        pending: set[asyncio.Task[Any]] = set()

        async def run() -> None:
            nonlocal running

            if closed or running:
                return

            running = True

            try:
                clicked = await check_turnstile(
                    page,
                    timeout_ms=options.timeout_ms,
                    selectors=options.selectors,
                    max_candidates_per_selector=options.max_candidates_per_selector,
                    foreground=options.foreground,
                    click_delay_ms=options.click_delay_ms,
                    mouse_move_steps=options.mouse_move_steps,
                    wait_after_click_ms=options.wait_after_click_ms,
                )

                if clicked:
                    await _log(options, "turnstile candidate clicked")
            except Exception as error:
                await _log(options, str(error))
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


async def _log(options: TurnstileAutoOptions, message: str) -> None:
    if not options.logger:
        return

    result = options.logger(message)
    if inspect.isawaitable(result):
        await result
