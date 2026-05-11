from __future__ import annotations

from typing import Any

import patchright.sync_api as _patchright_sync_api
from patchright.sync_api import *  # noqa: F403
from patchright.sync_api import Browser, BrowserContext, Page, Playwright
from patchright.sync_api import sync_playwright as _patchright_sync_playwright

from ._turnstile_options import TurnstileAutoOptions, TurnstileOption
from .headless import (
    get_headless_user_agent,
    with_default_user_agent,
    with_headless_user_agent,
)
from .main_world import install_main_world_evaluate_defaults
from .turnstile_sync import check_turnstile, install_turnstile_auto_solver

_MISSING = object()


class BrowserWrapper:
    def __init__(
        self,
        browser: Browser,
        default_turnstile: TurnstileOption | None = None,
        default_user_agent: str | None = None,
    ) -> None:
        self._browser = browser
        self._default_turnstile = default_turnstile
        self._default_user_agent = default_user_agent

    def new_context(self, **kwargs: Any) -> BrowserContext:
        turnstile = kwargs.pop("turnstile", _MISSING)
        context_options = with_default_user_agent(kwargs, self._default_user_agent)
        context = self._browser.new_context(**context_options)
        turnstile_option = (
            self._default_turnstile if turnstile is _MISSING or turnstile is None else turnstile
        )

        if turnstile_option:
            install_turnstile_auto_solver(context, turnstile_option)

        return context

    def new_page(self, **kwargs: Any) -> Page:
        turnstile = kwargs.pop("turnstile", _MISSING)
        page_options = with_default_user_agent(kwargs, self._default_user_agent)
        page = self._browser.new_page(**page_options)
        turnstile_option = (
            self._default_turnstile if turnstile is _MISSING or turnstile is None else turnstile
        )

        if turnstile_option:
            install_turnstile_auto_solver(page.context, turnstile_option)

        return page

    def __getattr__(self, name: str) -> Any:
        return getattr(self._browser, name)

    def __enter__(self) -> "BrowserWrapper":
        enter = getattr(self._browser, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, *args: Any) -> Any:
        exit_ = getattr(self._browser, "__exit__", None)
        if callable(exit_):
            return exit_(*args)
        self._browser.close()
        return None

    def __repr__(self) -> str:
        return f"BrowserWrapper({self._browser!r})"


class BrowserTypeWrapper:
    def __init__(self, browser_type: Any) -> None:
        self._browser_type = browser_type

    def launch(self, **kwargs: Any) -> BrowserWrapper:
        turnstile = kwargs.pop("turnstile", None)
        default_user_agent = (
            None if kwargs.get("headless") is False else get_headless_user_agent(kwargs)
        )
        browser = self._browser_type.launch(**kwargs)

        return BrowserWrapper(browser, turnstile, default_user_agent)

    def launch_persistent_context(
        self,
        user_data_dir: str,
        **kwargs: Any,
    ) -> BrowserContext:
        turnstile = kwargs.pop("turnstile", None)
        context_options = with_headless_user_agent(kwargs)
        context = self._browser_type.launch_persistent_context(
            user_data_dir,
            **context_options,
        )

        if turnstile:
            install_turnstile_auto_solver(context, turnstile)

        return context

    def __getattr__(self, name: str) -> Any:
        return getattr(self._browser_type, name)

    def __repr__(self) -> str:
        return f"BrowserTypeWrapper({self._browser_type!r})"


class PlaywrightWrapper:
    def __init__(self, playwright: Playwright) -> None:
        self._playwright = playwright

    @property
    def chromium(self) -> BrowserTypeWrapper:
        return BrowserTypeWrapper(self._playwright.chromium)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._playwright, name)

    def __repr__(self) -> str:
        return f"PlaywrightWrapper({self._playwright!r})"


class PlaywrightContextManager:
    def __init__(self) -> None:
        install_main_world_evaluate_defaults()
        self._manager = _patchright_sync_playwright()

    def __enter__(self) -> PlaywrightWrapper:
        return PlaywrightWrapper(self._manager.__enter__())

    def __exit__(self, *args: Any) -> Any:
        return self._manager.__exit__(*args)

    def start(self) -> PlaywrightWrapper:
        return PlaywrightWrapper(self._manager.start())


def sync_playwright() -> PlaywrightContextManager:
    return PlaywrightContextManager()


__all__ = sorted(
    set(getattr(_patchright_sync_api, "__all__", []))
    | {
    "BrowserTypeWrapper",
    "BrowserWrapper",
    "PlaywrightContextManager",
    "PlaywrightWrapper",
    "TurnstileAutoOptions",
    "TurnstileOption",
    "check_turnstile",
    "get_headless_user_agent",
    "install_main_world_evaluate_defaults",
    "install_turnstile_auto_solver",
    "sync_playwright",
    }
)
