"""A ChatGPT scraper on Bright Data's Scraper API."""

from .scrape import (
    CHATGPT,
    ApiError,
    Outcome,
    TokenMissing,
    ask,
    ask_one,
    fetch,
    run,
    scrape,
    status,
    token,
    trigger,
    write,
)

__all__ = [
    "CHATGPT",
    "ApiError",
    "Outcome",
    "TokenMissing",
    "ask",
    "ask_one",
    "fetch",
    "run",
    "scrape",
    "status",
    "token",
    "trigger",
    "write",
]
__version__ = "0.1.0"
