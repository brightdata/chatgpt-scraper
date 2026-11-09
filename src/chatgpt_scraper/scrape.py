"""ChatGPT answers, citations and sources on the Bright Data Scraper API.

    prompt -> trigger -> poll progress -> fetch snapshot -> ChatGPT's answer

Standard library only. The Python SDK wraps this scraper but sends no
`require_sources`, so this module talks to the API over HTTP and passes every
input the scraper accepts. Every call is an asynchronous job: trigger it, poll
until the snapshot is ready, download it. On 2026-11-09 an answer took 65 to
282 seconds.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.brightdata.com/datasets/v3"

#: The one ChatGPT scraper: a prompt in, ChatGPT's answer out, with its citations.
CHATGPT = "gd_m7aof0k82r803d5bjm"

#: Every prompt is sent to this URL. The scraper requires it as an input.
CHATGPT_URL = "https://chatgpt.com/"

#: The slowest answer on 2026-11-09 took 282 seconds; the wait outlasts that comfortably.
TIMEOUT = 900
POLL_SECONDS = 10

NO_TOKEN = (
    "API token required but not found.\n"
    "  export BRIGHTDATA_API_TOKEN=YOUR_API_KEY   token: https://brightdata.com/cp/setting/users\n"
    "  or run once: npx -p @brightdata/cli bdata login"
)


class ApiError(Exception):
    """The API refused a request, or a job ended without a snapshot."""


class TokenMissing(ApiError):
    """No token in the environment and no Bright Data CLI login."""


def _cli_credentials() -> Path:
    """Where `bdata login` stores the key, the same path the Python SDK reads."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "brightdata-cli" / "credentials.json"


def token() -> str:
    """BRIGHTDATA_API_TOKEN, else the Bright Data CLI login. Never a key in code."""
    found = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
    if found:
        return found
    try:
        found = json.loads(_cli_credentials().read_text(encoding="utf-8")).get("api_key", "")
    except (OSError, ValueError, AttributeError):
        found = ""
    if not found:
        raise TokenMissing(NO_TOKEN)
    return found


def _call(path: str, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise ApiError(f"HTTP {exc.code}: {detail[:300]}") from None


def trigger(
    dataset_id: str,
    inputs: list[dict[str, Any]],
    *,
    discover_by: str | None = None,
    limit_per_input: int | None = None,
) -> str:
    """Start a job and return its snapshot id. Error rows are always asked for."""
    query: dict[str, Any] = {"dataset_id": dataset_id, "include_errors": "true"}
    if discover_by:
        query.update(type="discover_new", discover_by=discover_by)
    if limit_per_input is not None:
        query["limit_per_input"] = limit_per_input
    return _call("/trigger?" + urllib.parse.urlencode(query), inputs)["snapshot_id"]


def status(snapshot_id: str) -> str:
    """running, ready or failed."""
    return _call(f"/progress/{snapshot_id}")["status"]


def fetch(snapshot_id: str) -> list[dict[str, Any]]:
    """The rows of a ready snapshot. Snapshots stay downloadable for 30 days."""
    data = _call(f"/snapshot/{snapshot_id}?format=json")
    return [row for row in (data if isinstance(data, list) else [data]) if isinstance(row, dict)]


def _poll(snapshot_id: str) -> str:
    """status(), except that a dropped connection is not the end of a paid job.

    A poll is safe to repeat. A Node run of this same loop lost a job to one
    "fetch failed" on 2026-10-24, five minutes in. An HTTP error still raises.
    """
    try:
        return status(snapshot_id)
    except (urllib.error.URLError, OSError):
        return "running"


def run(
    dataset_id: str,
    inputs: list[dict[str, Any]],
    *,
    discover_by: str | None = None,
    limit_per_input: int | None = None,
    timeout: float = TIMEOUT,
) -> list[dict[str, Any]]:
    """Trigger, wait, fetch. Rows the API could not collect carry an `error` key."""
    snapshot_id = trigger(
        dataset_id, inputs, discover_by=discover_by, limit_per_input=limit_per_input
    )
    deadline = time.monotonic() + timeout
    while (state := _poll(snapshot_id)) not in ("ready", "failed"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"timeout: snapshot {snapshot_id} not ready after {timeout:.0f}s")
        time.sleep(POLL_SECONDS)
    if state == "failed":
        raise ApiError(f"snapshot {snapshot_id} failed")
    return fetch(snapshot_id)


def _many(value: str | Iterable[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _set(**fields: Any) -> dict[str, Any]:
    """Only the fields that were actually set."""
    return {name: value for name, value in fields.items() if value is not None}


def ask(
    prompts: str | Iterable[str],
    country: str = "US",
    *,
    web_search: bool | None = None,
    require_sources: bool | None = None,
    additional_prompt: str | None = None,
    **options: Any,
) -> list[dict[str, Any]]:
    """ChatGPT's answer to each prompt, one record per prompt, one job for the list.

    `web_search` asks ChatGPT to search the web, `require_sources` asks for
    cited sources, and `additional_prompt` is a follow-up asked in the same
    chat. `options` go into each input as the API names them, such as `index`.
    """
    extra = _set(
        country=country.upper() if country else None,
        web_search=web_search,
        require_sources=require_sources,
        additional_prompt=additional_prompt,
        **options,
    )
    items = [{"url": CHATGPT_URL, "prompt": prompt, **extra} for prompt in _many(prompts)]
    return run(CHATGPT, items)


def split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Records, and the error messages of the rows that are not records."""
    records = [row for row in rows if not row.get("error")]
    errors = [str(row["error"]) for row in rows if row.get("error")]
    return records, errors


@dataclass
class Outcome:
    """What happened to one prompt."""

    prompt: str
    answer: dict[str, Any] | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def line(self) -> str:
        """One line a reader can understand without having read the source."""
        label = self.prompt if len(self.prompt) <= 50 else self.prompt[:47] + "..."
        if not self.ok:
            return f"failed  {label!r}: {self.error}"
        text = self.answer.get("answer_text") or ""
        cited = len(self.answer.get("citations") or [])
        return f"got     {label!r}: {len(text):,} characters, {cited} citations"


def ask_one(prompt: str, country: str = "US", web_search: bool | None = None) -> Outcome:
    """Ask one prompt. Never raises for a bad prompt: a failure becomes an Outcome.

    A missing token is the exception, because it fails every prompt the same way.
    """
    outcome = Outcome(prompt=prompt)
    try:
        found, errors = split(ask(prompt, country, web_search=web_search))
    except TokenMissing:
        raise
    except Exception as exc:  # one bad prompt must not end the run
        outcome.error = str(exc) if isinstance(exc, (ApiError, TimeoutError)) else (
            f"{type(exc).__name__}: {exc}"
        )
        return outcome
    if found:
        outcome.answer = found[0]
    else:
        outcome.error = "; ".join(dict.fromkeys(errors)) or "no answer and no error row"
    return outcome


def scrape(
    prompts: Iterable[str], country: str = "US", web_search: bool | None = None
) -> list[Outcome]:
    """Ask every prompt and return one Outcome each, in order."""
    return [ask_one(prompt, country, web_search) for prompt in prompts]


def write(outcomes: list[Outcome], path: str | Path, country: str = "US") -> Path:
    """Write one JSON file: when it ran, and ChatGPT's answer per prompt."""
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": country.upper(),
        "prompts": [{"prompt": o.prompt, "answer": o.answer} for o in outcomes],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
