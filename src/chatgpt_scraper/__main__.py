"""chatgpt-scraper "best crm for startups", or python -m chatgpt_scraper "best crm for startups" """

from __future__ import annotations

import argparse
import re
import sys
import threading
import time
from contextlib import contextmanager

from .scrape import TokenMissing, ask_one, token, write

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def country_code(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z]{2}", value):
        raise argparse.ArgumentTypeError(f"{value!r} is not a two-letter country code, like US")
    return value.upper()


@contextmanager
def waiting(label: str):
    """A spinner and a running clock, so minutes of waiting look alive.

    Outside a terminal it prints one plain line instead: a log wants a line,
    not an animation.
    """
    if not sys.stdout.isatty():
        print(f"asking  {label}...", flush=True)
        yield
        return
    done = threading.Event()
    started = time.monotonic()

    def spin() -> None:
        frame = 0
        while not done.wait(0.1):
            secs = int(time.monotonic() - started)
            clock = f"{secs // 3600}:{secs // 60 % 60:02d}:{secs % 60:02d}"
            sys.stdout.write(f"\r\033[2K{FRAMES[frame % len(FRAMES)]} {label} {clock}")
            sys.stdout.flush()
            frame += 1

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        sys.stdout.write("\r\033[2K")  # leave the line clean for the result
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chatgpt-scraper",
        description="Ask ChatGPT one or more prompts and save its answers with their citations.",
    )
    parser.add_argument("prompts", nargs="+", help="what you would type into ChatGPT, quoted")
    parser.add_argument("--country", type=country_code, default="US",
                        help="two-letter country ChatGPT answers from, default %(default)s")
    parser.add_argument("--web-search", action="store_true",
                        help="ask ChatGPT to search the web before answering")
    parser.add_argument("--out", default="chatgpt.json", help="output file, default %(default)s")
    args = parser.parse_args(argv)

    print(
        f"Asking ChatGPT {len(args.prompts)} prompt(s) from {args.country}"
        f"{', with web search' if args.web_search else ''}\n"
        "Usually one to five minutes each. Billed per answer, 5,000 free credits a month.",
        flush=True,  # piped, an unflushed header would print after the error below
    )
    try:
        token()  # fail before the first wait, not after it
    except TokenMissing as exc:
        print(exc, file=sys.stderr)
        return 2

    outcomes = []
    for prompt in args.prompts:
        label = prompt if len(prompt) <= 50 else prompt[:47] + "..."
        with waiting(repr(label)):
            outcome = ask_one(prompt, args.country, True if args.web_search else None)
        print(outcome.line(), flush=True)
        outcomes.append(outcome)

    path = write(outcomes, args.out, args.country)
    answered = sum(1 for o in outcomes if o.ok)
    print(f"\nSaved {answered} answers as JSON to {path}")
    return 0 if all(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
