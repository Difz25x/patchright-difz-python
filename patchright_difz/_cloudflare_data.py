from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TURNSTILE_RESPONSE_SELECTORS = [
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

CLOUDFLARE_FIELD_SELECTOR = (
    'input[name*="cf-" i], input[name*="cf_" i], input[name*="turnstile" i], '
    'textarea[name*="cf-" i], textarea[name*="cf_" i], '
    'textarea[name*="turnstile" i], [data-ray], [data-cf-ray], '
    "[data-sitekey], [data-cf-turnstile-response]"
)

DEFAULT_TOKEN_MIN_LENGTH = 20

CloudflareData = dict[str, Any]
CloudflareCookie = Any

CLOUDFLARE_DATA_SCRIPT = """
({
  responseSelectors,
  cloudflareFieldSelector,
  minTokenLength,
}) => {
  const responseData = [];
  const widgets = [];
  const fields = [];
  const iframeSources = [];
  const scriptSources = [];
  const sitekeys = [];
  const rayIds = [];

  const pushUnique = (target, value) => {
    if (value && !target.includes(value)) target.push(value);
  };

  const selectorFor = (element) => {
    const tag = element.tagName.toLowerCase();
    const id = element.getAttribute("id");
    const name = element.getAttribute("name");

    if (name) return `${tag}[name="${name}"]`;
    if (id) return `${tag}#${id}`;

    return tag;
  };

  const valueFor = (element) => {
    if (
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement
    ) {
      return element.value;
    }

    return (
      element.getAttribute("value") ??
      element.getAttribute("data-cf-turnstile-response") ??
      element.getAttribute("data-turnstile-response") ??
      element.getAttribute("data-turnstile-token") ??
      ""
    );
  };

  const addResponse = (element, source) => {
    const value = valueFor(element).trim();
    if (!value) return;

    const entry = {
      source,
      selector: selectorFor(element),
      name: element.getAttribute("name") ?? undefined,
      id: element.getAttribute("id") ?? undefined,
      value,
    };

    if (
      !responseData.some(
        (existing) =>
          existing.value === entry.value &&
          existing.selector === entry.selector,
      )
    ) {
      responseData.push(entry);
    }
  };

  for (const selector of responseSelectors) {
    try {
      document
        .querySelectorAll(selector)
        .forEach((element) =>
          addResponse(
            element,
            element.hasAttribute("data-cf-turnstile-response") ||
              element.hasAttribute("data-turnstile-response") ||
              element.hasAttribute("data-turnstile-token")
              ? "attribute"
              : "field",
          ),
        );
    } catch (_error) {}
  }

  document
    .querySelectorAll("[data-sitekey], .cf-turnstile")
    .forEach((element) => {
      const sitekey = element.getAttribute("data-sitekey") ?? undefined;
      const widget = {
        selector: selectorFor(element),
        id: element.getAttribute("id") ?? undefined,
        class_name: element.getAttribute("class") ?? undefined,
        sitekey,
        action: element.getAttribute("data-action") ?? undefined,
        cdata: element.getAttribute("data-cdata") ?? undefined,
        callback: element.getAttribute("data-callback") ?? undefined,
        theme: element.getAttribute("data-theme") ?? undefined,
        size: element.getAttribute("data-size") ?? undefined,
        language: element.getAttribute("data-language") ?? undefined,
      };

      widgets.push(widget);
      pushUnique(sitekeys, sitekey);
    });

  document.querySelectorAll("iframe").forEach((iframe) => {
    const src = iframe.getAttribute("src");
    if (!src || !/cloudflare|turnstile|challenge/i.test(src)) return;

    pushUnique(iframeSources, src);

    try {
      const parsed = new URL(src, location.href);
      pushUnique(sitekeys, parsed.searchParams.get("sitekey"));
      pushUnique(sitekeys, parsed.searchParams.get("siteKey"));
      pushUnique(sitekeys, parsed.searchParams.get("k"));
    } catch (_error) {}
  });

  document.querySelectorAll("script[src]").forEach((script) => {
    const src = script.getAttribute("src");
    if (src && /cloudflare|turnstile|challenge-platform/i.test(src)) {
      pushUnique(scriptSources, src);
    }
  });

  try {
    document.querySelectorAll(cloudflareFieldSelector).forEach((element) => {
      const value = valueFor(element).trim();
      const name = element.getAttribute("name") ?? undefined;
      const id = element.getAttribute("id") ?? undefined;
      const rayId =
        element.getAttribute("data-ray") ??
        element.getAttribute("data-cf-ray");

      pushUnique(rayIds, rayId);

      if (!value) return;

      fields.push({
        selector: selectorFor(element),
        name,
        id,
        value,
      });
    });
  } catch (_error) {}

  const collectStorage = (storage) => {
    const entries = [];

    for (let index = 0; index < storage.length; index++) {
      const key = storage.key(index);
      if (
        !key ||
        !/cloudflare|turnstile|cf[_-]|cfchl|cf_chl|challenge/i.test(key)
      ) {
        continue;
      }

      entries.push({
        key,
        value: storage.getItem(key) ?? "",
      });
    }

    return entries;
  };

  const safeCollectStorage = (getStorage) => {
    try {
      return collectStorage(getStorage());
    } catch (_error) {
      return [];
    }
  };

  const challengeOptions = (() => {
    try {
      const value = window._cf_chl_opt;
      return value === undefined ? null : JSON.parse(JSON.stringify(value));
    } catch (_error) {
      return null;
    }
  })();

  const tokens = responseData
    .map((response) => response.value)
    .filter((value) => value.length >= minTokenLength);
  const present =
    responseData.length > 0 ||
    widgets.length > 0 ||
    sitekeys.length > 0 ||
    iframeSources.some((src) => /turnstile/i.test(src));

  return {
    url: location.href,
    user_agent: navigator.userAgent,
    document_cookie_names: document.cookie
      .split(";")
      .map((part) => part.trim().split("=")[0])
      .filter(Boolean),
    turnstile: {
      present,
      solved: tokens.length > 0,
      responses: responseData,
      tokens,
      sitekeys,
      widgets,
      iframes: iframeSources,
      scripts: scriptSources,
    },
    challenge: {
      cleared: false,
      fields,
      ray_ids: rayIds,
      options: challengeOptions,
    },
    storage: {
      local: safeCollectStorage(() => localStorage),
      session: safeCollectStorage(() => sessionStorage),
    },
  };
}
"""


def cloudflare_data_arg(min_token_length: int = DEFAULT_TOKEN_MIN_LENGTH) -> dict[str, Any]:
    return {
        "responseSelectors": TURNSTILE_RESPONSE_SELECTORS,
        "cloudflareFieldSelector": CLOUDFLARE_FIELD_SELECTOR,
        "minTokenLength": min_token_length,
    }


def empty_cloudflare_page_data() -> CloudflareData:
    return {
        "url": None,
        "user_agent": None,
        "document_cookie_names": [],
        "turnstile": {
            "present": False,
            "solved": False,
            "responses": [],
            "tokens": [],
            "sitekeys": [],
            "widgets": [],
            "iframes": [],
            "scripts": [],
        },
        "challenge": {
            "cleared": False,
            "fields": [],
            "ray_ids": [],
            "options": None,
        },
        "storage": {
            "local": [],
            "session": [],
        },
    }


def build_cloudflare_data(
    page_data: Mapping[str, Any],
    cookies: Sequence[Any],
) -> CloudflareData:
    cloudflare_cookies = [
        cookie for cookie in cookies if is_cloudflare_cookie(cookie)
    ]
    clearance_cookie = next(
        (
            cookie
            for cookie in cloudflare_cookies
            if cookie_name(cookie) == "cf_clearance"
        ),
        None,
    )
    turnstile = dict(page_data["turnstile"])
    challenge = dict(page_data["challenge"])

    turnstile["tokens"] = unique_strings(turnstile.get("tokens", []))
    turnstile["sitekeys"] = unique_strings(turnstile.get("sitekeys", []))
    turnstile["iframes"] = unique_strings(turnstile.get("iframes", []))
    turnstile["scripts"] = unique_strings(turnstile.get("scripts", []))
    challenge["cleared"] = bool(clearance_cookie)

    return {
        "url": page_data.get("url"),
        "user_agent": page_data.get("user_agent"),
        "document_cookie_names": page_data.get("document_cookie_names", []),
        "cookies": list(cookies),
        "cloudflare_cookies": cloudflare_cookies,
        "clearance_cookie": clearance_cookie,
        "turnstile": turnstile,
        "challenge": challenge,
        "storage": page_data["storage"],
    }


def cookie_name(cookie: Any) -> str:
    if isinstance(cookie, Mapping):
        value = cookie.get("name", "")
    else:
        value = getattr(cookie, "name", "")

    return str(value)


def is_cloudflare_cookie(cookie: Any) -> bool:
    return cookie_name(cookie).lower().startswith(("__cf", "_cf", "cf_"))


def normalize_cookie_urls(urls: str | Sequence[str] | None) -> str | list[str] | None:
    if urls is None or isinstance(urls, str):
        return urls

    return list(urls)


def unique_strings(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if not value:
            continue

        text = str(value)
        if text in seen:
            continue

        seen.add(text)
        result.append(text)

    return result
