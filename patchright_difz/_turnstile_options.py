from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence, Union

DEFAULT_TURNSTILE_SELECTORS = [
    '[name="cf-turnstile-response"]',
    'input[name="cf-turnstile-response"]',
    'iframe[src*="challenges.cloudflare.com"]',
    'iframe[title*="Cloudflare"]',
    'iframe[title*="challenge"]',
    ".cf-turnstile",
    "[data-sitekey]",
    "[data-cf-turnstile-response]",
]

FALLBACK_SELECTORS = ["iframe", "div", "button", '[role="checkbox"]']
FALLBACK_LIMIT = 80


@dataclass(frozen=True)
class TurnstileAutoOptions:
    timeout_ms: int = 5000
    interval_ms: int = 2000
    selectors: Sequence[str] = tuple(DEFAULT_TURNSTILE_SELECTORS)
    max_candidates_per_selector: int = 5
    logger: Optional[Callable[[str], Any]] = None


TurnstileOption = Union[bool, Mapping[str, Any], TurnstileAutoOptions]


def normalize_options(option: TurnstileOption | None) -> TurnstileAutoOptions:
    if isinstance(option, TurnstileAutoOptions):
        return option

    source: Mapping[str, Any] = option if isinstance(option, Mapping) else {}

    return TurnstileAutoOptions(
        timeout_ms=int(_read_option(source, "timeout_ms", "timeoutMs", 5000)),
        interval_ms=int(_read_option(source, "interval_ms", "intervalMs", 2000)),
        selectors=list(_read_option(source, "selectors", "selectors", DEFAULT_TURNSTILE_SELECTORS)),
        max_candidates_per_selector=int(
            _read_option(
                source,
                "max_candidates_per_selector",
                "maxCandidatesPerSelector",
                5,
            )
        ),
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
