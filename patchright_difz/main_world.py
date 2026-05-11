from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from patchright._impl._frame import Frame as ImplFrame
from patchright._impl._js_handle import JSHandle as ImplJSHandle
from patchright._impl._locator import Locator as ImplLocator
from patchright._impl._page import Page as ImplPage
from patchright._impl._page import Worker as ImplWorker
from patchright.async_api import Error as AsyncError
from patchright.async_api import Frame as AsyncFrame
from patchright.async_api import JSHandle as AsyncJSHandle
from patchright.async_api import Locator as AsyncLocator
from patchright.async_api import Page as AsyncPage
from patchright.async_api import Worker as AsyncWorker
from patchright.async_api import _generated as async_generated
from patchright.sync_api import Error as SyncError
from patchright.sync_api import Frame as SyncFrame
from patchright.sync_api import JSHandle as SyncJSHandle
from patchright.sync_api import Locator as SyncLocator
from patchright.sync_api import Page as SyncPage
from patchright.sync_api import Worker as SyncWorker
from patchright.sync_api import _generated as sync_generated

F = TypeVar("F", bound=Callable[..., Any])

_PATCHED_ATTR = "__patchright_difz_main_world_patches__"


def install_main_world_evaluate_defaults() -> bool:
    sync_methods = [
        (SyncPage, "evaluate"),
        (SyncPage, "evaluate_handle"),
        (SyncFrame, "evaluate"),
        (SyncFrame, "evaluate_handle"),
        (SyncLocator, "evaluate"),
        (SyncLocator, "evaluate_handle"),
        (SyncLocator, "evaluate_all"),
        (SyncJSHandle, "evaluate"),
        (SyncJSHandle, "evaluate_handle"),
        (SyncWorker, "evaluate"),
        (SyncWorker, "evaluate_handle"),
    ]
    async_methods = [
        (AsyncPage, "evaluate"),
        (AsyncPage, "evaluate_handle"),
        (AsyncFrame, "evaluate"),
        (AsyncFrame, "evaluate_handle"),
        (AsyncLocator, "evaluate"),
        (AsyncLocator, "evaluate_handle"),
        (AsyncLocator, "evaluate_all"),
        (AsyncJSHandle, "evaluate"),
        (AsyncJSHandle, "evaluate_handle"),
        (AsyncWorker, "evaluate"),
        (AsyncWorker, "evaluate_handle"),
    ]
    impl_methods = [
        (ImplPage, "evaluate"),
        (ImplPage, "evaluate_handle"),
        (ImplFrame, "evaluate"),
        (ImplFrame, "evaluate_handle"),
        (ImplFrame, "eval_on_selector_all"),
        (ImplLocator, "evaluate"),
        (ImplLocator, "evaluate_handle"),
        (ImplLocator, "evaluate_all"),
        (ImplJSHandle, "evaluate"),
        (ImplJSHandle, "evaluate_handle"),
        (ImplWorker, "evaluate"),
        (ImplWorker, "evaluate_handle"),
    ]

    for cls, method_name in sync_methods:
        _patch_keyword_default(cls, method_name, "isolated_context", False)

    for cls, method_name in async_methods:
        _patch_async_keyword_default(cls, method_name, "isolated_context", False)

    for cls, method_name in impl_methods:
        _patch_async_keyword_default(cls, method_name, "isolatedContext", False)

    _patch_sync_eval_on_selector(SyncPage)
    _patch_sync_eval_on_selector(SyncFrame)
    _patch_async_eval_on_selector(AsyncPage)
    _patch_async_eval_on_selector(AsyncFrame)
    _patch_sync_eval_on_selector_all(SyncPage, is_page=True)
    _patch_sync_eval_on_selector_all(SyncFrame, is_page=False)
    _patch_async_eval_on_selector_all(AsyncPage, is_page=True)
    _patch_async_eval_on_selector_all(AsyncFrame, is_page=False)

    return True


def _patch_keyword_default(
    cls: type[Any],
    method_name: str,
    keyword_name: str,
    default: Any,
) -> None:
    if _is_patched(cls, f"{method_name}:{keyword_name}"):
        return

    original = getattr(cls, method_name, None)
    if not callable(original):
        return

    @wraps(original)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if keyword_name not in kwargs or kwargs[keyword_name] is None:
            kwargs[keyword_name] = default
        return original(self, *args, **kwargs)

    setattr(cls, method_name, wrapper)
    _mark_patched(cls, f"{method_name}:{keyword_name}")


def _patch_async_keyword_default(
    cls: type[Any],
    method_name: str,
    keyword_name: str,
    default: Any,
) -> None:
    if _is_patched(cls, f"{method_name}:{keyword_name}"):
        return

    original = getattr(cls, method_name, None)
    if not callable(original):
        return

    @wraps(original)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if keyword_name not in kwargs or kwargs[keyword_name] is None:
            kwargs[keyword_name] = default
        return await original(self, *args, **kwargs)

    setattr(cls, method_name, wrapper)
    _mark_patched(cls, f"{method_name}:{keyword_name}")


def _patch_sync_eval_on_selector(cls: type[Any]) -> None:
    patch_id = "eval_on_selector:main_world"
    if _is_patched(cls, patch_id):
        return

    def eval_on_selector(
        self: Any,
        selector: str,
        expression: str,
        arg: Any = None,
        *,
        strict: bool | None = None,
    ) -> Any:
        handle = self.query_selector(selector, strict=strict)

        if not handle:
            raise SyncError(f'Failed to find element matching selector "{selector}"')

        try:
            return handle.evaluate(expression, arg, isolated_context=False)
        finally:
            handle.dispose()

    setattr(cls, "eval_on_selector", eval_on_selector)
    _mark_patched(cls, patch_id)


def _patch_async_eval_on_selector(cls: type[Any]) -> None:
    patch_id = "eval_on_selector:main_world"
    if _is_patched(cls, patch_id):
        return

    async def eval_on_selector(
        self: Any,
        selector: str,
        expression: str,
        arg: Any = None,
        *,
        strict: bool | None = None,
    ) -> Any:
        handle = await self.query_selector(selector, strict=strict)

        if not handle:
            raise AsyncError(f'Failed to find element matching selector "{selector}"')

        try:
            return await handle.evaluate(expression, arg, isolated_context=False)
        finally:
            await handle.dispose()

    setattr(cls, "eval_on_selector", eval_on_selector)
    _mark_patched(cls, patch_id)


def _patch_sync_eval_on_selector_all(cls: type[Any], *, is_page: bool) -> None:
    patch_id = "eval_on_selector_all:main_world"
    if _is_patched(cls, patch_id):
        return

    def eval_on_selector_all(
        self: Any,
        selector: str,
        expression: str,
        arg: Any = None,
    ) -> Any:
        if is_page:
            return self.main_frame.eval_on_selector_all(selector, expression, arg)

        return sync_generated.mapping.from_maybe_impl(
            self._sync(
                self._impl_obj.eval_on_selector_all(
                    selector=selector,
                    expression=expression,
                    arg=sync_generated.mapping.to_impl(arg),
                    isolatedContext=False,
                )
            )
        )

    setattr(cls, "eval_on_selector_all", eval_on_selector_all)
    _mark_patched(cls, patch_id)


def _patch_async_eval_on_selector_all(cls: type[Any], *, is_page: bool) -> None:
    patch_id = "eval_on_selector_all:main_world"
    if _is_patched(cls, patch_id):
        return

    async def eval_on_selector_all(
        self: Any,
        selector: str,
        expression: str,
        arg: Any = None,
    ) -> Any:
        if is_page:
            return await self.main_frame.eval_on_selector_all(selector, expression, arg)

        return async_generated.mapping.from_maybe_impl(
            await self._impl_obj.eval_on_selector_all(
                selector=selector,
                expression=expression,
                arg=async_generated.mapping.to_impl(arg),
                isolatedContext=False,
            )
        )

    setattr(cls, "eval_on_selector_all", eval_on_selector_all)
    _mark_patched(cls, patch_id)


def _patched_set(cls: type[Any]) -> set[str]:
    patches = cls.__dict__.get(_PATCHED_ATTR)
    if isinstance(patches, set):
        return patches

    patches = set()
    setattr(cls, _PATCHED_ATTR, patches)
    return patches


def _is_patched(cls: type[Any], patch_id: str) -> bool:
    return patch_id in _patched_set(cls)


def _mark_patched(cls: type[Any], patch_id: str) -> None:
    _patched_set(cls).add(patch_id)
