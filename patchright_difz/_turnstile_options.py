from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence, Union

OPTIONAL_TURNSTILE_RESPONSE_SELECTORS = [
    '[name="cf-turnstile-response"]',
    'input[name="cf-turnstile-response"]',
    'textarea[name="cf-turnstile-response"]',
    'input[name="turnstile-response"]',
    'textarea[name="turnstile-response"]',
    'input[name="turnstile-token"]',
    'textarea[name="turnstile-token"]',
    "[data-cf-turnstile-response]",
    "[data-turnstile-response]",
    "[data-turnstile-token]",
]

DEFAULT_TURNSTILE_SELECTORS = [
    'iframe[src*="challenges.cloudflare.com"]',
    'iframe[title*="Cloudflare"]',
    'iframe[title*="challenge"]',
    ".cf-turnstile",
    "[data-sitekey]",
    *OPTIONAL_TURNSTILE_RESPONSE_SELECTORS,
]

FALLBACK_SELECTORS = ["iframe", "div", "button", '[role="checkbox"]']
FALLBACK_LIMIT = 80


@dataclass(frozen=True)
class TurnstileAutoOptions:
    timeout_ms: int = 3000
    interval_ms: int = 750
    selectors: Sequence[str] = tuple(DEFAULT_TURNSTILE_SELECTORS)
    max_candidates_per_selector: int = 5
    foreground: bool = True
    click_delay_ms: int = 35
    mouse_move_steps: int = 8
    wait_after_click_ms: int = 150
    logger: Optional[Callable[[str], Any]] = None


TurnstileOption = Union[bool, Mapping[str, Any], TurnstileAutoOptions]


def normalize_options(option: TurnstileOption | None) -> TurnstileAutoOptions:
    if isinstance(option, TurnstileAutoOptions):
        return option

    source: Mapping[str, Any] = option if isinstance(option, Mapping) else {}

    return TurnstileAutoOptions(
        timeout_ms=int(_read_option(source, "timeout_ms", "timeoutMs", 3000)),
        interval_ms=int(_read_option(source, "interval_ms", "intervalMs", 750)),
        selectors=list(_read_option(source, "selectors", "selectors", DEFAULT_TURNSTILE_SELECTORS)),
        max_candidates_per_selector=int(
            _read_option(
                source,
                "max_candidates_per_selector",
                "maxCandidatesPerSelector",
                5,
            )
        ),
        foreground=bool(_read_option(source, "foreground", "foreground", True)),
        click_delay_ms=int(_read_option(source, "click_delay_ms", "clickDelayMs", 35)),
        mouse_move_steps=int(_read_option(source, "mouse_move_steps", "mouseMoveSteps", 8)),
        wait_after_click_ms=int(_read_option(source, "wait_after_click_ms", "waitAfterClickMs", 150)),
        logger=_read_option(source, "logger", "logger", None),
    )


def _read_option(
    source: Mapping[str, Any],
    snake_name: str,
    camel_name: str,
    default: Any,
) -> Any:
    if snake_name in source:
        return source[snake_name]
    if camel_name in source:
        return source[camel_name]
    return default
