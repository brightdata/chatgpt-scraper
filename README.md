# ChatGPT scraper for Python

Scrape ChatGPT answers, citations and sources to JSON with Python. Track brand visibility in ChatGPT. No OpenAI API key.
Built on the [Bright Data ChatGPT Scraper API](https://brightdata.com/products/web-scraper/chatgpt?utm_source=github&utm_medium=referral&utm_content=chatgpt-scraper). New accounts get 5,000 free credits a month.

[![Live check](https://github.com/brightdata/chatgpt-scraper/actions/workflows/live.yml/badge.svg)](https://github.com/brightdata/chatgpt-scraper/actions/workflows/live.yml)
[![last verified](https://img.shields.io/badge/last%20verified-10%20Nov%202026-brightgreen)](https://github.com/brightdata/chatgpt-scraper/actions/workflows/live.yml) <!-- verified: rewritten by the daily run -->

[Quickstart](#how-to-scrape-chatgpt-results-with-python) · [No OpenAI key](#scrape-chatgpt-without-an-openai-api-key) · [CLI](#bulk-chatgpt-prompt-scraper-cli) · [Citations](#track-chatgpt-citations-and-brand-visibility-for-a-prompt) · [Endpoints](#scrape-chatgpt-answers-citations-and-sources) · [Data](#chatgpt-answer-data-fields-json) · [Errors](#chatgpt-scraper-errors) · [MCP and Claude Code](#chatgpt-mcp-server-and-claude-code-skill) · [Free credits](#is-this-chatgpt-scraper-free) · [Docs](https://docs.brightdata.com/products/scrapers/chatgpt/introduction) · [Support](#support)

ChatGPT answers as JSON, in Python: send a prompt, get back the answer ChatGPT
shows in its own interface, as text, Markdown and HTML, with the sites it
cited, by country, with web search and follow-up prompts. Built for ChatGPT
visibility tracking and GEO: which brands ChatGPT mentions and recommends, and
which sources it cites. No OpenAI API key, no browser, no dependencies. Built on the
[Bright Data ChatGPT Scraper API](https://brightdata.com/products/web-scraper/chatgpt?utm_source=github&utm_medium=referral&utm_content=chatgpt-scraper).

Also here: a one-command CLI for a list of prompts, and the
[Bright Data CLI](#chatgpt-mcp-server-and-claude-code-skill), which needs no Python at all.

## How to scrape ChatGPT results with Python

Python 3.10 or newer, and nothing to install: this is the standard library.

```bash
export BRIGHTDATA_API_TOKEN=YOUR_API_KEY
```

Get a token from the
[Bright Data control panel](https://brightdata.com/cp/setting/users). No
account yet? [Create one](https://brightdata.com/cp/start); new accounts get
[5,000 free credits a month](https://docs.brightdata.com/general/account/billing-and-pricing/free-tier).

```python
import json
import os
import time
import urllib.request

API = "https://api.brightdata.com/datasets/v3"
HEADERS = {
    "Authorization": f"Bearer {os.environ['BRIGHTDATA_API_TOKEN']}",
    "Content-Type": "application/json",
}


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(API + path, data=data, headers=HEADERS)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


prompt = {
    "url": "https://chatgpt.com/",
    "prompt": "Best CRM software for small businesses",
    "country": "US",
    "web_search": True,
}
job = call("/trigger?dataset_id=gd_m7aof0k82r803d5bjm&include_errors=true", [prompt])
while call(f"/progress/{job['snapshot_id']}")["status"] not in ("ready", "failed"):
    time.sleep(10)
answer = call(f"/snapshot/{job['snapshot_id']}?format=json")[0]
if "error" in answer:
    raise SystemExit(answer["error"])
print(answer["answer_text"][:120])
for citation in (answer["citations"] or [])[:3]:
    print("cited:", citation["url"])
```

```
The best CRM software for a small business depends on whether you primarily need to manage customers, track sales, gener
cited: https://www.hubspot.com/products/crm?utm_source=chatgpt.com
cited: https://www.zoho.com/crm/?utm_source=chatgpt.com
cited: https://www.pipedrive.com/?utm_source=chatgpt.com
```

Expect one to five minutes: the API asks ChatGPT and the loop waits for the
answer. One run with web search and sources took eleven. Billed
[per answer](https://brightdata.com/pricing/web-scraper).

Three things in that snippet are not optional.

`url` must be `https://chatgpt.com/`. The scraper requires it on every input;
the prompt goes in `prompt`.

`web_search: true` asks ChatGPT to search the web, which is what usually
brings citations. Without it, `citations` can come back `null` rather than an
empty list, so the loop guards for that.

`include_errors=true` makes the API report a failed prompt as a row with an
`error` key. The API default is off.

The Bright Data [Python SDK](https://github.com/brightdata/sdk-python) wraps this scraper, but it does not send `require_sources`, so it cannot ask ChatGPT to cite. Hence the
plain HTTP, here and in this package.

## Scrape ChatGPT without an OpenAI API key

The ChatGPT Scraper API needs no OpenAI account, no OpenAI API key and no
ChatGPT login. The only credential is a Bright Data API key, set as
`BRIGHTDATA_API_TOKEN`. This package and its command also find the key stored
by `bdata login`.

It returns what a person sees in ChatGPT itself, not what the OpenAI API
returns: the answer with its citations, links, shopping and map blocks, as
ChatGPT renders them for that country.

## Bulk ChatGPT prompt scraper CLI

The command in this repo runs the quickstart for several prompts at once and
writes one JSON file.

```bash
pip install git+https://github.com/brightdata/chatgpt-scraper
chatgpt-scraper "Best CRM software for small businesses" "Best project management tool for startups" --web-search
```

```
Asking ChatGPT 2 prompt(s) from US, with web search
Usually one to five minutes each. Billed per answer, 5,000 free credits a month.
asking  'Best CRM software for small businesses'...
got     'Best CRM software for small businesses': 3,416 characters, 11 citations
asking  'Best project management tool for startups'...
got     'Best project management tool for startups': 2,903 characters, 0 citations

Saved 2 answers as JSON to chatgpt.json
```

In a terminal the `asking` lines are replaced by a spinner and a running
clock, updating in place, so you can see it is working and how long it has
been going.

```
--country CC   two-letter country ChatGPT answers from, default US
--web-search   ask ChatGPT to search the web before answering
--out PATH     output file, default chatgpt.json
```

`python -m chatgpt_scraper` works too. The command finds the token in
`BRIGHTDATA_API_TOKEN`, or, if you ran `npx -p @brightdata/cli bdata login`
once, in the stored login, for you and for any coding agent in that terminal.

Import it instead of running it, for `ok` and `error` per prompt instead of
raw rows. `scrape` never raises for one bad prompt; check `ok` before reading
`answer`:

```python
from chatgpt_scraper import scrape

for outcome in scrape(["Best running shoes for beginners", "Best free photo editing app"]):
    if outcome.ok:
        print(f"{outcome.prompt}: {outcome.answer['answer_text'][:60]}")
    else:
        print(f"{outcome.prompt} failed: {outcome.error}")
```

```
Best running shoes for beginners: If you're just getting into running, I'd recommend shoes tha
Best free photo editing app: Best overall free app Snapseed Snapseed Free on iPhone and A
```

## Scrape ChatGPT answers, citations and sources

There is one ChatGPT scraper, documented in the
[ChatGPT Scraper API docs](https://docs.brightdata.com/products/scrapers/chatgpt/introduction).
Every snippet below is complete: paste it as is after the `pip install`
above. Every one of them runs in Actions each Monday, a smaller check runs
every other day, and the badge at the top is the latest result.

| you want | how |
| --- | --- |
| ChatGPT's answer to prompts | `ask(["prompt one", "prompt two"], "US")` |
| the sites ChatGPT cites | `ask(prompt, web_search=True, require_sources=True)` |
| a follow-up in the same chat | `ask(prompt, additional_prompt="...")` |
| the answer from another country | `ask(prompt, "DE")` |
| the answer as Markdown | `answer_text_markdown` on any answer |

`ask` takes one prompt or a list. A list is one job, not one per prompt.
Each answer is one record, and a prompt the API could not answer comes back
as a row with an `error` key. Any other input the API accepts goes in as the
API names it, such as `index`.

### Track ChatGPT citations and brand visibility for a prompt

```python
from urllib.parse import urlparse

from chatgpt_scraper import ask

answer = ask("Best project management software for remote teams", web_search=True, require_sources=True)[0]
domains = [urlparse(c["url"]).netloc for c in answer["citations"]]
print(len(domains), "citations from", len(set(domains)), "sites:")
for domain in sorted(set(domains))[:5]:
    print(" ", domain, domains.count(domain))
```

```
10 citations from 9 sites:
  asana.com 2
  basecamp.com 1
  clickup.com 1
  monday.com 1
  resources.rework.com 1
```

`require_sources` asks ChatGPT to cite, and `web_search` makes it look.
`citations` holds each cited `url` with its `title`; `links_attached` holds the
links inside the answer text. Asking the same prompt every day is how GEO
tools track share of citations over time.

### Ask ChatGPT a follow-up prompt

```python
from chatgpt_scraper import ask

answer = ask(
    "Name three popular sourdough bread recipes",
    additional_prompt="Which of them is easiest for a beginner? One sentence.",
)[0]
print("first: ", answer["answer_text"][:80])
print("second:", answer["additional_answer_text"][:80])
```

```
first:  Here are three popular sourdough bread recipes: 1. Classic Artisan Sourdough Bre
second: Sourdough sandwich bread is the easiest for beginners because it's soft, forgivi
```

The follow-up runs in the same chat, so it can refer to the first answer. Its
answer lands in `additional_answer_text`, with its own
`citations_additional_prompt`.

### Compare ChatGPT answers by country

```python
from chatgpt_scraper import ask

for country in ("US", "DE"):
    answer = ask("Which supermarket chain has the cheapest groceries?", country, web_search=True)[0]
    print(country, "|", answer["answer_text"][:90])
```

```
US | ALDI is generally the cheapest traditional supermarket chain in the U.S. , according to 20
DE | In Germany, Aldi, Lidl, Netto and Penny are generally the cheapest supermarket chains. The
```

`country` is the two-letter country ChatGPT answers from. The US answer named
ALDI; the German one named Aldi, Lidl, Netto and Penny. `geolocation` is also accepted, but on
9 Nov 2026 coordinates for Midtown Manhattan got an answer about Houston that
began "Since your precise location isn't available", so this package does not
document it.

### Get ChatGPT's answer as Markdown

```python
from pathlib import Path

from chatgpt_scraper import ask

answer = ask("Explain what a REST API is, with one short code example")[0]
markdown = answer["answer_text_markdown"]
Path("answer.md").write_text(markdown, encoding="utf-8")
lines = markdown.splitlines()
headings = [line for line, under in zip(lines, lines[1:]) if under and set(under) == {"-"}]
print(len(markdown), "characters saved to answer.md; headings:", headings)
```

```
1854 characters saved to answer.md; headings: ['How a REST API works', 'Short code example', 'In simple terms']
```

`answer_text_markdown` is converted from the rendered page: headings are
underlined with dashes rather than written with `#`, tables are pipe tables,
and code is indented four spaces under a line naming the language, not
fenced. `answer_text` is the same answer as plain text, and `answer_html` the
full page, about 1.4 MB.

### Trigger now, fetch later

For a long list of prompts, do not block a process for an hour. Trigger, keep
the snapshot id, fetch when ready. Snapshots stay downloadable for 30 days.

```python
import time

from chatgpt_scraper import CHATGPT, fetch, status, trigger

item = {"url": "https://chatgpt.com/", "prompt": "What is the capital of Australia?", "country": "US"}
snapshot = trigger(CHATGPT, [item])
print("snapshot:", snapshot)
while (state := status(snapshot)) not in ("ready", "failed"):
    time.sleep(10)
print("status:", state)
print("fetched:", fetch(snapshot)[0]["answer_text"][:60])
```

```
snapshot: sd_mw9bv3ophde91g5k7
status: ready
fetched: The capital of Australia is Canberra . 🇦🇺 It is located in t
```

The input fields the live API accepted on 2026-11-09, for dataset
`gd_m7aof0k82r803d5bjm`:

| input | required | what it does |
| --- | --- | --- |
| `url` | yes | always `https://chatgpt.com/` |
| `prompt` | yes | the question |
| `country` | no | two-letter country ChatGPT answers from |
| `web_search` | no | `true` asks ChatGPT to search the web |
| `require_sources` | no | `true` asks ChatGPT to cite sources |
| `additional_prompt` | no | a follow-up in the same chat |
| `index` | no | your own number, returned on the record |
| `geolocation` | no | `"lat,long"`; not honoured in our tests |

`bdata pipelines info gd_m7aof0k82r803d5bjm collect_by_url` prints the input
fields the API validates.

## ChatGPT answer data fields (JSON)

The fields most people want from an answer:

```
prompt  answer_text  answer_text_markdown  citations  links_attached  country  web_search_triggered
```

`web_search_triggered` does not follow the `web_search` input: on
9 Nov 2026 it read `false` for an answer with ten citations and `true` for a
prompt sent without `web_search`. `model` was `null` on every record. The code
hardcodes no field list. Whatever the API returns lands in each record, and
in the command's file.

<!-- fields:start -->
Regenerated every day from the published schema,
[scrapers-full.json](https://docs.brightdata.com/scrapers-full.json), so they cannot go stale. A record
carries the fields that apply to it, plus `timestamp` and `input`; the
sample file's first answer has 33 keys.

<details>
<summary>All 32 ChatGPT answer fields, <code>gd_m7aof0k82r803d5bjm</code></summary>

| field | type | description |
| --- | --- | --- |
| `url` | url | ChatGPT page URL |
| `prompt` | text | The input prompt |
| `answer_html` | text | The answer of ChatGPT search |
| `answer_text` | text | Answer text in plain text |
| `links_attached` | array | Hyperlinks included in the response text, along with their position and linked words. |
| `citations` | array | Sources directly referenced in the answer, often linked to specific facts or claims. |
| `country` | country | Country from which to perform the search |
| `is_map` | boolean | Indication whether a map package result was generated |
| `references` | array | Links grouped under the References section |
| `shopping` | array | Product recommendation cards from ChatGPT's Shopping panel |
| `shopping_visible` | boolean | Whether the Shopping panel appeared for this answer |
| `index` | number | The index column lets you assign a unique ID to each crawl request for easy tracking. |
| `answer_text_markdown` | html2markdown | Answer text in markdown format. |
| `web_search_triggered` | boolean | Was a web search triggered by ChatGPT when returning the answer |
| `additional_prompt` | text | The additional_prompt is a follow-up input sent after receiving the first answer, aiming to clarify, expand, or refine the initial response. The system processes this prompt and returns the result as additional_answer_text. |
| `additional_answer_text` | text | The additional_answer_text is the system's response to the additional_prompt, which follows the initial interaction. It provides additional information, clarification, or a refined answer based on the user's follow-up input. |
| `map` | array | Map package result |
| `search_sources` | array | A list of external web pages ChatGPT used to gather information, usually shown at the bottom of the response. |
| `search_sources_more` | array | A list of external web pages ChatGPT used to gather information, usually shown at the bottom of the response (from "More" partition). |
| `response_raw` | text | Raw data of ChatGPT's response |
| `response_raw_additional_prompt` | text | Raw data of ChatGPT's response for additional prompt. |
| `answer_section_html` | text | The answer's section html |
| `model` | text | Model used for answer |
| `web_search_query` | array | Model-generated web search queries (exact strings, in execution order) |
| `prompt_sent_at` | date | exact prompt timestamp |
| `answer_text_raw` | text | Original answer_text as extracted, without trimming or whitespace normalization (may include leading/trailing spaces and newline characters). |
| `business_locations` | array | Please consider adding new fields, attaching example of JSON we can get for each business location mentioned in answer. Array of business location entities returned when the answer includes local business results. Each entry contains the business ID, coordinates, name, category, address, contact info, ratings, hours, images, and open/closed status. |
| `ads` | array | Array of advertisement's card data. |
| `additional_answer_text_markdown` | html2markdown | additional_answer_text_markdown in markdown format. |
| `questionnaire` | array | Questionnaire |
| `shopping_additional_prompt` | array | Product recommendation cards from ChatGPT's Shopping panel from results of additional prompt |
| `citations_additional_prompt` | array | Sources directly referenced in the answer of additional prompt, often linked to specific facts or claims. |

</details>
<!-- fields:end -->

<details>
<summary>The start of a real output file, from <code>chatgpt-scraper "Best CRM software for small businesses"</code></summary>

Each line is cut at 160 characters here; `answer_html` alone is a 1.4 MB line.

```json
{
  "generated_at": "2026-11-09T14:00:41.695758+00:00",
  "country": "US",
  "prompts": [
    {
      "prompt": "Best CRM software for small businesses",
      "answer": {
        "url": "https://chatgpt.com/?q=Best%20CRM%20software%20for%20small%20businesses",
        "prompt": "Best CRM software for small businesses",
        "answer_html": "<html class=\"x108lcm5 xzx5cyk xojncy5 xy3g5xu x1nktip0 xwbwmuu x1it3fuk xh8yej3 xuu8av0 xeuugli xgs08xk x1javzw2 xfqjyog x1rob05q xvmah...
        "answer_text": "The best CRM software for a small business depends on whether you need to manage leads, track sales, automate follow-ups, manage custome...
        "links_attached": [
          {
            "url": "https://www.hubspot.com/products/crm?utm_source=chatgpt.com",
            "text": "HubSpot website",
            "position": 1
          },
          {
            "url": "https://www.zoho.com/crm/?utm_source=chatgpt.com",
            "text": "Zoho website",
  ...
```

The whole file, one answer with every field, is
[examples/sample_output.json](examples/sample_output.json).

</details>

## ChatGPT scraper errors

| you see | what it means |
| --- | --- |
| `API token required but not found.` | Exit 2, before any request. Set the token, or run `bdata login`. |
| `failed  'prompt': ...` | Exit 1. The API returned an error row for that prompt instead of an answer. The message is the API's. |
| `failed  'prompt': timeout: snapshot ... not ready after 900s` | Exit 1. Run it again, or fetch the snapshot later with `fetch()`. |
| `failed  'prompt': HTTP 401: ...` | The token is set but wrong. |

Any failure exits 1, so a run is safe to gate a script on.

From the functions, the same conditions look like this:

| you see | what it means |
| --- | --- |
| `TokenMissing` | No `BRIGHTDATA_API_TOKEN` and no `bdata login`. |
| `ApiError: HTTP 400: ...validation_error...` | An input the API does not accept. The message names the field. |
| a row with an `error` key | The API's answer for one prompt. The other rows are fine. |
| `TimeoutError` | The job outlived the 900-second wait. Pass `timeout=` to `run`, or use `trigger` and fetch later. |

## ChatGPT MCP server and Claude Code skill

No Python, nothing installed. Paste both lines; the first opens a browser
once, or use `bdata login --device` over SSH and in CI:

```bash
npx -p @brightdata/cli bdata login
npx -p @brightdata/cli bdata pipelines run gd_m7aof0k82r803d5bjm collect_by_url --url "https://chatgpt.com/" --prompt "Best CRM software for small businesses" --country US --pretty
```

1 record, 19 fields, 75 seconds on 9 Nov 2026. The CLI leaves out fields that
are null. The record is about 3 MB of JSON, mostly `answer_html`.

`npx skills add brightdata/skills` teaches Claude Code, Cursor and Codex these
commands and the docs, so plain language works afterwards. Full guide:
[Bright Data for your coding agent](https://docs.brightdata.com/quickstart-coding-agent).

No terminal, for a hosted assistant? The
[Bright Data MCP server](https://github.com/brightdata/brightdata-mcp#which-tool-to-use)
runs any pre-built scraper, ChatGPT included, through `search_scrapers` and
`run_scraper` in its `scrapers` group:

    https://mcp.brightdata.com/mcp?token=YOUR_API_TOKEN&groups=scrapers

An agent can also open the account itself, no signup form:
[agent registration](https://brightdata.com/auth.md). Everything else Bright
Data connects to, from LangChain to Zapier and n8n:
[integrations](https://docs.brightdata.com/integrations/introduction).

## Is this ChatGPT scraper free?

New Bright Data accounts get
[5,000 free credits a month](https://docs.brightdata.com/general/account/billing-and-pricing/free-tier).
The ChatGPT scraper bills per record, one per answer.
[Pricing](https://brightdata.com/pricing/web-scraper) lists the rates.

## Support

Bugs in this repo:
[open an issue](https://github.com/brightdata/chatgpt-scraper/issues), and
[CONTRIBUTING.md](CONTRIBUTING.md) says what to put in it.
Anything about the API, your account or your credits:
[Bright Data support](https://brightdata.zendesk.com/hc/en-us/requests/new).

## License

[Apache 2.0](LICENSE).

## ChatGPT scraper for Node.js

The same ChatGPT scraper is available for Node.js: [brightdata/chatgpt-scraper-node](https://github.com/brightdata/chatgpt-scraper-node).

## More open source scrapers from Bright Data

Other Python scrapers built the same way, with live-verified examples:

- [URL to Markdown (Fetch API) for Python](https://github.com/brightdata/fetch-api-scraper)
- [YouTube scraper for Python](https://github.com/brightdata/youtube-scraper)
- [LinkedIn scraper for Python](https://github.com/brightdata/linkedin-scraper)
