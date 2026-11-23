# PERKESO AI Prototype

A local prototype that layers AI features on a mirrored copy of [perkeso.gov.my](https://www.perkeso.gov.my).
Nothing here is affiliated with or endorsed by PERKESO.

## Features

| Feature | Where | Endpoint |
|---|---|---|
| **Cari Skim** – find the right scheme | Assistant panel (bottom-right) | – |
| **Tuntutan** – claim cards + AI personal checklist | Assistant panel | `POST /api/checklist` |
| **Tanya** – chat answering only from PERKESO pages (BM25 retrieval, cited sources) | Assistant panel | `POST /api/chat` |
| **Kalkulator** – contribution calculator (local, no AI) | Assistant panel | `POST /api/caruman` |
| **🌐 Faham laman ini** – explain/translate the current page into 8 languages | Bar under the banner on every page | `POST /api/explain` |

IC numbers and long digit runs are stripped before any text is sent to a model. Model output is never inserted as raw HTML.

## Requirements

- Python 3.10+ (stdlib only, no `pip install`)
- `curl` on PATH (used by the mirror/crawl scripts)
- [OmniRoute](https://github.com/diegosouzapw/OmniRoute) running locally – an OpenAI-compatible router to free models

## 1. Connect the AI models (OmniRoute)

1. Install and start OmniRoute:
   ```bash
   npm install -g omniroute
   omniroute            # dashboard + API on http://localhost:20128
   ```
2. Open the dashboard at http://localhost:20128 and connect the free providers used by the default chain
   (OpenRouter free, Cloudflare `cfp`, DuckDuckGo `ddgw`). Any provider works as long as the model IDs
   below match what the dashboard lists.
3. Create an API key in the dashboard.
4. Configure the prototype:
   ```bash
   cp .env.example .env
   # edit .env: paste OMNIROUTE_API_KEY, adjust OMNIROUTE_MODELS if needed
   ```
5. Check the connection:
   ```bash
   curl http://localhost:20128/v1/models -H "Authorization: Bearer $OMNIROUTE_API_KEY"
   ```

**How models are used:** `server.py` tries `OMNIROUTE_MODELS` in order. A model that errors, times out
(30 s to first token) or emits a fake tool call is benched for 60 s and the next one is tried.
Free models are slow (20–40 s per answer) and quality varies by language.

**Using another provider:** any OpenAI-compatible `/chat/completions` endpoint works – set `OMNIROUTE_URL`,
`OMNIROUTE_API_KEY` and `OMNIROUTE_MODELS` to that provider's base URL, key and model names.

## 2. Build the local site

The mirrored site is not committed (~150 MB). Regenerate it:

```bash
python mirror.py           # homepage -> site/index.html + assets
python mirror.py --kb      # every page in kb/pages.json (takes ~10 min)
```

`kb/pages.json` (the knowledge base) is committed. To refresh it from the live site: `python crawl.py`.

## 3. Run

```bash
python server.py           # http://localhost:8080
```

The assistant button appears at the bottom-right of every page; the translate bar sits under the top banner.

## Evaluation

```bash
python eval/run.py         # server must be running; writes eval/results/<timestamp>.json
```

## Layout

```
server.py        HTTP server, retrieval, model chain, /api/* endpoints
assistant/       widget injected into every page (assistant.js, assistant.css)
caruman.py       contribution calculator
crawl.py         builds kb/pages.json from the live site
mirror.py        mirrors pages + assets into site/
kb/              knowledge base (pages.json, Act PDFs)
eval/            question set + grader
snapshots/       screenshots of each feature
```
