# For coding agents working in this repository

Read this before changing anything. Every line below was verified against the
live API, `brightdata-sdk` 2.5.2 or the Bright Data CLI 0.4.1 on 2026-11-09.
Where the API reference pages disagree with the live API, the live API is what
is written here.

## Auth

- `token()` reads `BRIGHTDATA_API_TOKEN`, then the key `bdata login` stored in
  `brightdata-cli/credentials.json` (the same file the Python SDK reads).
  Setting the variable, or running the login once, is the one step a human
  must do; never paste a key into code.
- The raw HTTP Quickstart in the README reads `BRIGHTDATA_API_TOKEN` only. It
  does not see the CLI login.

## How the API behaves

- One dataset, `gd_m7aof0k82r803d5bjm`, collect only. Every input needs
  `url: "https://chatgpt.com/"` and a `prompt`.
- The Python SDK wraps it but sends no `require_sources`. This package calls
  `https://api.brightdata.com/datasets/v3` with the standard library and has
  no dependencies. Keep it that way.
- Every call is an asynchronous job: `/trigger`, poll `/progress/<id>`, then
  `/snapshot/<id>?format=json`. Answers took 44 to 282 seconds; one with
  `web_search` and `require_sources` took 667. `TIMEOUT` is 900.
- A status poll that fails with a network error is retried until the
  deadline. An HTTP error still raises.
- Always send `include_errors=true`.
- Live behaviour on 2026-11-09:
  - Without `web_search`, `citations` can be `null`, not `[]` (one run), or
    a full list (another run). Guard for `null`.
  - `web_search_triggered` does not follow the input: `false` on an answer
    with ten citations, `true` on a prompt sent without `web_search`.
  - `model` is `null` on every record.
  - `geolocation` ("40.7484,-73.9857", Midtown Manhattan) got an answer about
    Houston, "Since your precise location isn't available". Do not document
    it as working.
  - `answer_text_markdown` is html2text style: setext headings, pipe tables,
    code indented four spaces under a bare language line, never fenced.
  - `answer_html` is the full page, about 1.4 MB on one line. The README
    excerpt cuts every line at 160 characters for that reason; the test does
    the same.
- The schema changes without notice. Never hardcode a field list.
- The full documentation index, one `.md` page per entry:
  https://docs.brightdata.com/llms.txt

## Working here

- `pytest` runs offline and needs no token. `ruff check .` must pass.
- CI follows the README's own commands on an empty machine, finding its
  sections by their exact H2 text. Rename a heading in ci.yml too.
- A weekly workflow executes every fenced block in the README against the real
  API, and the same run also does a smaller live check. A snippet must be complete
  and paste-able on its own, and its shown output must be real.
- The field table in the README sits between `<!-- fields:start -->` and
  `<!-- fields:end -->` and is regenerated weekly by
  `.github/scripts/field_tables.py` from
  https://docs.brightdata.com/scrapers-full.json. Do not edit it by hand.
- The "last verified" badge line at the top of the README is rewritten by the
  weekly run. Do not edit it by hand.
- Headings are written for search: "ChatGPT scraper for Python", "How to scrape ...". Keep that
  pattern when adding a section.
- Keep it small. Beyond the status poll, do not add retries, deduplication,
  scheduling, databases, async examples or concurrency.
