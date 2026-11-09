"""These run without a token. The API is a stub."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

import chatgpt_scraper.__main__ as cli

# the package exports a function named scrape, which hides the module of that name
gpt = sys.modules["chatgpt_scraper.scrape"]

ROOT = Path(__file__).resolve().parents[1]
PROMPT = "Best CRM software for small businesses"


class FakeApi:
    """Answers trigger, progress and snapshot the way the live API does."""

    def __init__(self, rows=None, states=("ready",)):
        self.rows = rows or []
        self.states = list(states)
        self.calls = []

    def __call__(self, path, body=None):
        self.calls.append((path, body))
        if path.startswith("/trigger"):
            return {"snapshot_id": "sd_test"}
        if path.startswith("/progress/"):
            return {"status": self.states.pop(0) if len(self.states) > 1 else self.states[0]}
        if path.startswith("/snapshot/"):
            return self.rows
        raise AssertionError(path)

    def trigger(self):
        path, body = self.calls[0]
        return dict(urllib.parse.parse_qsl(path.split("?", 1)[1])), body


@pytest.fixture
def api(monkeypatch):
    def install(**kwargs):
        fake = FakeApi(**kwargs)
        monkeypatch.setattr(gpt, "_call", fake)
        monkeypatch.setattr(gpt, "POLL_SECONDS", 0)
        return fake

    return install


@pytest.fixture
def no_login(monkeypatch, tmp_path):
    """No token in the environment and no CLI login: the stranger's machine."""
    monkeypatch.delenv("BRIGHTDATA_API_TOKEN", raising=False)
    monkeypatch.setattr(gpt, "_cli_credentials", lambda: tmp_path / "missing.json")


def test_a_prompt_is_sent_to_chatgpt_with_its_country_and_nothing_unset(api):
    fake = api()
    gpt.ask(PROMPT, "us")

    query, body = fake.trigger()
    assert query == {"dataset_id": gpt.CHATGPT, "include_errors": "true"}
    assert body == [{"url": "https://chatgpt.com/", "prompt": PROMPT, "country": "US"}]


def test_every_option_goes_in_as_the_api_names_it(api):
    fake = api()
    gpt.ask(
        [PROMPT, "Name three sourdough recipes"],
        "GB",
        web_search=True,
        require_sources=True,
        additional_prompt="Which is easiest?",
        index=7,
    )
    _, body = fake.trigger()
    extra = {
        "country": "GB",
        "web_search": True,
        "require_sources": True,
        "additional_prompt": "Which is easiest?",
        "index": 7,
    }
    assert body == [
        {"url": "https://chatgpt.com/", "prompt": PROMPT, **extra},
        {"url": "https://chatgpt.com/", "prompt": "Name three sourdough recipes", **extra},
    ]


def test_web_search_false_is_sent_not_dropped(api):
    """False is a choice; only None means "leave it to the API"."""
    fake = api()
    gpt.ask(PROMPT, web_search=False)
    assert fake.trigger()[1][0]["web_search"] is False


def test_run_polls_until_the_snapshot_is_ready(api):
    fake = api(rows=[{"answer_text": "HubSpot"}], states=("running", "running", "ready"))
    assert gpt.run(gpt.CHATGPT, [{"prompt": "x"}]) == [{"answer_text": "HubSpot"}]
    assert [p for p, _ in fake.calls].count("/progress/sd_test") == 3


def test_a_dropped_poll_does_not_lose_the_job(api, monkeypatch):
    fake = api(rows=[{"answer_text": "HubSpot"}])
    dropped = []

    def flaky(path, body=None):
        if path.startswith("/progress/") and not dropped:
            dropped.append(path)
            raise urllib.error.URLError("connection reset")
        return fake(path, body)

    monkeypatch.setattr(gpt, "_call", flaky)
    assert gpt.run(gpt.CHATGPT, [{"prompt": "x"}]) == [{"answer_text": "HubSpot"}]
    assert dropped


def test_a_failed_snapshot_is_an_error(api):
    api(states=("failed",))
    with pytest.raises(gpt.ApiError, match="sd_test failed"):
        gpt.run(gpt.CHATGPT, [{"prompt": "x"}])


def test_a_job_that_never_finishes_times_out(api):
    api(states=("running",))
    with pytest.raises(TimeoutError, match="timeout"):
        gpt.run(gpt.CHATGPT, [{"prompt": "x"}], timeout=0)


def test_an_http_error_names_the_status_and_the_reason(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "test")

    def refuse(request, timeout):
        body = io.BytesIO(b'{"errors":[["prompt","This value is required"]]}')
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(gpt.urllib.request, "urlopen", refuse)
    with pytest.raises(gpt.ApiError, match="HTTP 400.*prompt"):
        gpt.trigger(gpt.CHATGPT, [{"url": "https://chatgpt.com/"}])


def test_the_token_comes_from_the_environment_then_the_cli_login(monkeypatch, tmp_path, no_login):
    with pytest.raises(gpt.TokenMissing, match="export BRIGHTDATA_API_TOKEN"):
        gpt.token()

    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({"api_key": "from-login"}), encoding="utf-8")
    monkeypatch.setattr(gpt, "_cli_credentials", lambda: credentials)
    assert gpt.token() == "from-login"

    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "from-env")
    assert gpt.token() == "from-env"


def test_an_answer_reports_its_length_and_citations(api):
    api(rows=[{"answer_text": "x" * 1234, "citations": [{}, {}, {}]}])
    outcome = gpt.ask_one(PROMPT)

    assert outcome.ok
    assert outcome.line() == f"got     {PROMPT!r}: 1,234 characters, 3 citations"


def test_an_error_row_fails_the_prompt_and_a_long_prompt_is_shortened(api):
    long_prompt = "Compare every CRM on the market by price, features and support quality"
    api(rows=[{"error": "Crawler error: something", "error_code": "crawl_error"}])
    outcome = gpt.ask_one(long_prompt)

    assert not outcome.ok
    assert outcome.line() == f"failed  {long_prompt[:47] + '...'!r}: Crawler error: something"


def test_one_bad_prompt_does_not_end_the_run(monkeypatch):
    def ask(prompt, country, web_search=None):
        if prompt == "boom":
            raise RuntimeError("boom")
        return [{"answer_text": prompt}]

    monkeypatch.setattr(gpt, "ask", ask)
    first, second = gpt.scrape(["boom", "hello"])

    assert first.error == "RuntimeError: boom"
    assert second.ok and second.answer == {"answer_text": "hello"}


def test_a_run_writes_what_it_found(api, tmp_path):
    api(rows=[{"answer_text": "HubSpot", "citations": []}])
    path = gpt.write(gpt.scrape([PROMPT], "gb"), tmp_path / "out.json", "gb")

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["country"] == "GB"
    assert document["prompts"] == [
        {"prompt": PROMPT, "answer": {"answer_text": "HubSpot", "citations": []}}
    ]
    assert document["generated_at"]


def fake_cli(monkeypatch, outcome_for, seen=None):
    monkeypatch.setattr(cli, "token", lambda: "test")

    def ask_one(prompt, country, web_search):
        if seen is not None:
            seen.append((prompt, country, web_search))
        return outcome_for(prompt)

    monkeypatch.setattr(cli, "ask_one", ask_one)


def test_the_cli_exit_code_says_whether_every_prompt_worked(monkeypatch, tmp_path):
    fake_cli(monkeypatch, lambda p: gpt.Outcome(p, answer={"answer_text": "x"}))
    assert cli.main([PROMPT, "--out", str(tmp_path / "ok.json")]) == 0

    fake_cli(monkeypatch, lambda p: gpt.Outcome(p, error="boom"))
    assert cli.main([PROMPT, "--out", str(tmp_path / "bad.json")]) == 1


def test_the_cli_passes_country_and_web_search(monkeypatch, tmp_path):
    seen = []
    fake_cli(monkeypatch, lambda p: gpt.Outcome(p, answer={"answer_text": "x"}), seen)
    cli.main([PROMPT, "--country", "de", "--web-search", "--out", str(tmp_path / "o.json")])
    cli.main([PROMPT, "--out", str(tmp_path / "o.json")])
    assert seen == [(PROMPT, "DE", True), (PROMPT, "US", None)]


def test_each_result_prints_before_the_next_prompt_starts(monkeypatch, tmp_path, capsys):
    fake_cli(monkeypatch, lambda p: gpt.Outcome(p, answer={"answer_text": "abc", "citations": [1]}))
    cli.main(["first", "second", "--out", str(tmp_path / "o.json")])

    out = capsys.readouterr().out.splitlines()
    assert [ln for ln in out if ln.startswith(("asking", "got"))] == [
        "asking  'first'...",
        "got     'first': 3 characters, 1 citations",
        "asking  'second'...",
        "got     'second': 3 characters, 1 citations",
    ]


def test_a_bad_country_is_refused_before_any_request(capsys):
    with pytest.raises(SystemExit):
        cli.main(["x", "--country", "USA"])
    assert "two-letter country code" in capsys.readouterr().err


def test_a_missing_token_is_a_message_not_a_traceback(no_login, capsys):
    assert cli.main([PROMPT]) == 2
    err = capsys.readouterr().err
    assert "export BRIGHTDATA_API_TOKEN" in err and "bdata login" in err
    assert "Traceback" not in err


def test_piped_output_keeps_the_header_before_the_error(tmp_path):
    """A log or an agent reads a pipe. The header must not land after the error."""
    env = {k: v for k, v in os.environ.items() if k != "BRIGHTDATA_API_TOKEN"}
    env["HOME"] = str(tmp_path)  # no CLI login: the stranger's machine
    env["APPDATA"] = str(tmp_path)
    run = subprocess.run(
        [sys.executable, "-m", "chatgpt_scraper", PROMPT],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )
    assert run.returncode == 2, run.stdout
    assert run.stdout.index("Asking ChatGPT") < run.stdout.index("API token required")


def test_the_readme_excerpt_is_the_start_of_the_example_file():
    """The README shows the first 20 lines of the real file, each cut at 160 characters.

    `answer_html` alone is a 1.4 MB line, so the excerpt cannot be verbatim.
    """
    sample = (ROOT / "examples" / "sample_output.json").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = [ln if len(ln) <= 160 else ln[:160] + "..." for ln in sample.splitlines()[:20]]

    assert "\n".join(lines) in readme, "README excerpt drifted from the file"
    assert "](examples/sample_output.json)" in readme


def test_every_in_page_link_has_its_heading():
    """A renamed heading would break the header row silently; the link check sees only URLs."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{1,6} (.+)$", readme, re.M)
    anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-") for h in headings}
    for anchor in re.findall(r"\]\(#([^)]+)\)", readme):
        assert anchor in anchors, f"#{anchor} points at no heading"
