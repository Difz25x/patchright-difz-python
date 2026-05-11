from __future__ import annotations

from .async_api import async_playwright
from .headless import get_headless_user_agent
from .main_world import install_main_world_evaluate_defaults
from .sync_api import sync_playwright

__version__ = "0.3.0"

install_main_world_evaluate_defaults()

__all__ = [
    "__version__",
    "async_playwright",
    "get_headless_user_agent",
    "install_main_world_evaluate_defaults",
    "sync_playwright",
]
