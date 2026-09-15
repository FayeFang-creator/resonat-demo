<div align="center">

# Sounds Like You

**An audio-first music discovery demo, built at HACKATUNE 2026 and kept running since**

Turn a listener's messy natural-language mood into explainable recommendations,
grounded in an offline audio-tag catalog and refined through lightweight taste memory.

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688.svg)](backend/README.md)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-646CFF.svg)](frontend/README.md)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](backend/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Origin & credits](#-origin-and-credit-where-it-is-due) · [How it works](#-how-it-works) · [Architecture](#-architecture) · [Dependencies](#-dependencies) · [Run](#-run-locally) · [API](#-api-surface) · [Verification](#-verification)

</div>

---

## 🏛️ Origin, and credit where it is due

This project was built at **[HACKATUNE 2026](https://munichmusiclabs.com/events/hackatune-2026/)**
(Munich Music Labs × Cyanite, Munich, 26–28 June 2026) — see also the
[TUM event page](https://www.tum.de/en/news-and-events/events/details/hackatune-2026-by-munich-music-labs).
Cyanite set the challenge: build audio-first, explainable music discovery on their
Search and Tagging API.

**Almost everything that makes this app interesting was built by the original team over that
weekend** — the confirmation gate, the like/dislike refill loop, the markdown taste-memory model,
the "Why this track?" explanation system, and the whole FastAPI orchestration behind them.

Original team, from the commit history of
[`Hurwitzzz/resonat_hackatune`](https://github.com/Hurwitzzz/resonat_hackatune) (89 commits):

- **[@Hurwitzzz](https://github.com/Hurwitzzz)** — Hewei Gao
- **[@CAgGen](https://github.com/CAgGen)**
- **[@baobaihong](https://github.com/baobaihong)** — Baihong Bao
- **[@johanna0626](https://github.com/johanna0626)** — Yihao Wang

The design system and UI mockups the frontend is built on came from a parallel repository by
**[@FayeFang-creator](https://github.com/FayeFang-creator)** during the same event.

That repository remains the record of the original work. **This one is a continuation, not a
replacement** — if you want to see what the team shipped at the hackathon, look there.

### Why this repository exists

After the event, the sponsor API was switched off — Cyanite's search and similarity endpoints
now return 404 and the issued key returns 401 — so the hackathon build stopped working: enter a
prompt, and the page dead-ends on an error. This repository exists to carry the project forward:

1. **Keep it runnable.** Search is re-implemented against a local, self-contained catalog of
   public Jamendo metadata, so the demo runs with **no API key and no external dependency** and
   will not rot when someone else's service goes away. See
   [Data and API notes](#-data-and-api-notes) for exactly what was traded away — this is tag
   matching, not the audio-semantic search Cyanite provided.
2. **Refine the frontend and the interaction design,** which is the ongoing work here.

No hackathon-provided dataset or Cyanite model output is included in this repository; per the
challenge agreement those may not be redistributed. The retrieval here does not need them.

---

## ✨ What is this?

Cochlea, also described in the product as **Sounds Like You**, is a hackathon music
recommendation app built around one principle: the user should understand why a
song was recommended.

The app takes a vague prompt such as "lonely midnight train ride", compiles it into
a visible Query Card, asks the user to confirm or refine that interpretation, then
searches a local Jamendo-derived catalog. User feedback updates an in-session seed set and,
when the round is finished, appends evidence to markdown-based taste memory.

This repository currently contains:

| Content | Description |
|---|---|
| [`frontend/`](frontend/) | React + TypeScript + Vite experience for prompt input, results, feedback, explanations, and "sounds like you" cards |
| [`backend/`](backend/) | FastAPI service that owns sessions, intent compilation, catalog search, explanations, and markdown memory |
| [`backend/data/`](backend/data/) | `demo_catalog.json` — public metadata for 2,401 Jamendo tracks (CC BY-SA); the only data source search uses |
| [`PRD-night.md`](PRD-night.md) | One-night sprint PRD that defines the confirmation gate, feedback loop, and no-database memory model |
| [`GETTING_STARTED.md`](GETTING_STARTED.md) | Chinese setup guide used by the team during development |

---

## 🧭 How it works

```mermaid
flowchart TD
    A["User prompt<br/>mood, scene, seed, or reference"] --> B["Whiteboard posts<br/>initial prompt + follow-ups"]
    B --> C["Intent compiler<br/>deterministic fallback or OpenAI-assisted"]
    C --> D["Query Card<br/>plain interpretation + free-text query + soft targets"]
    D --> E{"User confirms<br/>the interpretation?"}
    E -->|"No"| F["Add follow-up note"]
    F --> B
    E -->|"Yes"| G["Local catalog search<br/>IDF-weighted tag match"]
    G --> H["Visible recommendation cards"]
    H --> I{"User feedback"}
    I -->|"Like"| J["Record liked seed<br/>optionally refill with similar track"]
    I -->|"Dislike"| K["Remove card<br/>refill from liked seeds or backlog"]
    J --> L["Round finish"]
    K --> H
    L --> M["Append evidence.md<br/>liked track + final prompt + feel tags"]
    M --> N["Rewrite memory.md<br/>natural-language feel profile"]
    N --> C
    H --> O["Why this track?<br/>Jamendo tags + query card + ranking path"]
```

The recommendation loop is intentionally small:

| Step | What happens |
|---|---|
| **Intent** | `/intent` stores the first prompt as a whiteboard post and compiles a Query Card without searching yet |
| **Refine** | `/intent/follow-up` adds another post and recompiles the Query Card |
| **Confirm** | `/intent/confirm` runs the local catalog search only after the user accepts the interpretation |
| **Feedback** | `/feedback` records likes as seeds, removes disliked cards, and refills empty slots |
| **Memory** | `/round/finish` appends evidence and rewrites a feel-only profile in markdown |
| **Explain** | `/explain` builds an English explanation from the track's tags, the Query Card, user memory, and ranking metadata |

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Browser["Browser"]
        UI["React app<br/>StartPage + ResultsPage"]
        API["src/api.ts<br/>typed fetch wrapper"]
    end

    subgraph Backend["FastAPI backend"]
        APP["app.py<br/>HTTP schemas + routes"]
        ORCH["orchestrator.py<br/>session state machine"]
        INTENT["intent_agent.py<br/>Query Card + search args"]
        CAT["catalog.py<br/>local tag search"]
        EXPLAIN["explanation_builder.py<br/>Why this track"]
        MEM["memory.py<br/>evidence + feel profile"]
        RERANK["rerank.py<br/>refill ranking"]
    end

    subgraph LocalData["Local files"]
        JSON["backend/data/demo_catalog.json<br/>2401 tracks + tags"]
        MD["backend/memory/*.md<br/>runtime user memory"]
    end

    subgraph External["External services (optional)"]
        CDN["Jamendo audio CDN<br/>keyless, browser-direct"]
        OpenAI["OpenAI Responses API<br/>optional"]
    end

    UI --> API
    UI -.->|"audio"| CDN
    API -->|"/api"| APP
    APP --> ORCH
    ORCH --> INTENT
    ORCH --> CAT
    ORCH --> EXPLAIN
    ORCH --> MEM
    ORCH --> RERANK
    CAT --> JSON
    EXPLAIN --> OpenAI
    MEM --> MD
```

Session state lives in memory inside the backend process. Cross-session taste memory is
stored as two markdown files per user under `backend/memory/`; there is no database.

---

## 📁 Project structure

```text
.
├── backend/
│   ├── app.py                 # FastAPI routes and request/response contracts
│   ├── orchestrator.py        # prompt -> search -> feedback -> memory loop
│   ├── catalog.py             # local catalog search (replaces the retired Cyanite client)
│   ├── intent_agent.py        # Query Card and search-argument generation
│   ├── explanation_builder.py # grounded English recommendation explanations
│   ├── memory.py              # markdown evidence/profile storage
│   ├── rerank.py              # refill candidate ranking helpers
│   ├── build_catalog.py       # build-time: harvest the catalog from the public Jamendo API
│   └── data/demo_catalog.json # the local catalog that search runs against
│   └── test_*.py              # focused backend tests
├── frontend/
│   ├── src/App.tsx            # route shell
│   ├── src/pages/             # start and results flows
│   ├── src/components/        # cards, controls, modal, visual effects
│   └── src/api.ts             # typed API client for the FastAPI backend
├── start.sh                   # one-shot full-stack dev startup
├── dev.sh                     # smaller backend/frontend startup helper
├── serve.py                   # deploy entrypoint: one origin serves frontend + /api
├── Dockerfile                 # single-image deploy (HF Spaces or any container host)
└── .env.sample                # optional keys template
```

---

## 📦 Dependencies

| Layer | Runtime / package manager | Main dependencies |
|---|---|---|
| **Backend** | Python 3.13 + [`uv`](https://docs.astral.sh/uv/) | FastAPI, Uvicorn, Requests, HTTPX, python-dotenv, pytest |
| **Frontend** | Node.js 20+ + npm | React 19, React DOM, React Router, Vite, TypeScript, Tailwind CSS, motion, OGL, oxlint |
| **Data** | Local JSON | `backend/data/demo_catalog.json` (public Jamendo metadata, CC BY-SA) |
| **External APIs** | HTTP | None required at runtime; optional Jamendo download proxy, optional OpenAI Responses API |
| **Memory** | Markdown files | `backend/memory/<user_id>.evidence.md` and `backend/memory/<user_id>.memory.md` generated at runtime |

Backend dependency versions are locked by [`backend/uv.lock`](backend/uv.lock).
Frontend dependency versions are locked by [`frontend/package-lock.json`](frontend/package-lock.json).

---

## ⚙️ Configuration

**The demo needs no keys.** Just run it — everything below is an optional enhancement:

| Variable | Required? | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | Optional | Enables LLM-written interpretations and explanations. Without it, deterministic fallbacks run instead — fully functional, plainer copy |
| `OPENAI_MODEL` / `OPENAI_BASE_URL` / `OPENAI_TIMEOUT` | Optional | See [`backend/config.py`](backend/config.py) |
| `JAMENDO_CLIENT_ID` | Optional | Enables the high-quality download proxy; required to rebuild the catalog (`build_catalog.py`). A **public** identifier, not a secret — safe as a plain environment variable on your deploy platform |

Without `JAMENDO_CLIENT_ID` the download button returns 503; nothing else is affected.
`.env` is git-ignored and is loaded from the repository root by [`backend/config.py`](backend/config.py).

## 🚀 Run locally

Install the base tools first:

```bash
uv --version
node --version
npm --version
```

One command starts the whole app:

```bash
./start.sh
```

It syncs backend dependencies, installs frontend dependencies, starts FastAPI on
`:8000`, and starts Vite on `:5173`.

| URL | What it is |
|---|---|
| http://localhost:5173 | Frontend app |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | FastAPI Swagger UI |

Smaller commands are available through [`dev.sh`](dev.sh):

```bash
./dev.sh          # sync backend dependencies only
./dev.sh run      # run FastAPI on :8000
./dev.sh front    # run Vite on :5173
```

Manual equivalents:

```bash
# Backend
cd backend
uv sync
uv run uvicorn app:app --reload --port 8000
```

```bash
# Frontend
cd frontend
npm install
npm run dev
```

### Run it the way it is deployed (single origin, no Vite)

```bash
cd frontend && npm run build && cd .. && uv run --project backend uvicorn serve:root --port 7860
```

Open http://localhost:7860 — the frontend and `/api` share one origin, exactly as in production.

### Deploy

[`Dockerfile`](Dockerfile) builds a single image (frontend build + backend + local catalog)
listening on `7860`, which maps directly onto Hugging Face Spaces' Docker SDK. Any container
host works too.

```bash
docker build -t sounds-like-you . && docker run -p 7860:7860 sounds-like-you
```

**No secrets to configure.** To enable high-quality downloads, add `JAMENDO_CLIENT_ID` as a
plain environment variable (it is a public identifier, not a secret).

---

## 🔌 API surface

| Endpoint | Purpose |
|---|---|
| `GET /health` | Lightweight backend health check |
| `POST /intent` | Start a session and compile the first Query Card |
| `POST /intent/follow-up` | Add a follow-up note and recompile the Query Card |
| `POST /intent/confirm` | Run the confirmed catalog search and return cards |
| `POST /feedback` | Apply like/dislike feedback and refill the visible list |
| `POST /round/finish` | Persist liked evidence and rewrite the user feel profile |
| `POST /explain` | Generate "Why this track?" for a visible recommendation |
| `GET /your-sound` | Return the user's markdown feel profile |
| `GET /sounds-like-you` | Search for tracks that match the long-term profile |
| `POST /explain-sounds-like-you` | Explain a profile-based track |
| `GET /download/{track_id}` | Proxy a Jamendo MP3 download (needs `JAMENDO_CLIENT_ID`) |

In development the frontend reaches these routes through Vite's `/api` proxy; in production
[`serve.py`](serve.py) mounts the backend at `/api` on the same origin, so browser code always
uses relative paths such as `/api/intent`.

## 🧪 Verification

The backend tests are fully offline — search never touches the network, and the LLM seams are
monkeypatched:

```bash
cd backend
uv run pytest
```

Frontend checks:

```bash
cd frontend
npm run build
npm run lint
```

Basic runtime smoke checks:

```bash
./start.sh
curl localhost:8000/health
```

Expected health response:

```json
{"ok":true}
```

Self-check the retrieval layer on its own (no network):

```bash
cd backend && uv run python catalog.py
```

End to end: open `http://localhost:5173`, enter a prompt, confirm the Query Card, then
like/dislike and open "Why this track?". Try two semantically distant prompts (for example
`lonely midnight train ride` vs `sunny morning workout energy`) — the results should differ
noticeably.

---

## 🎧 Data and API notes

> **Post-hackathon status (September 2026):** Cyanite's `private-alpha` search and similarity
> endpoints are gone (404) and the issued key is revoked (401). Retrieval was therefore moved to
> a local catalog inside this repository, and **no API key is needed any more**.

| Id | Meaning |
|---|---|
| `track_id` | Jamendo numeric track id — used for audio, display and download |
| `cyanite_id` | Legacy field name; now **equal to** `track_id` (the dual-id scheme is gone, the frontend contract is unchanged) |

All retrieval happens inside [`backend/catalog.py`](backend/catalog.py), with zero network calls:

| Former Cyanite capability | How it works now |
|---|---|
| Text prompt search | `search_by_prompt()` — IDF-weighted tag and term matching, plus a speed band |
| Single-seed similarity | `find_similar()` — IDF-weighted nearest neighbours over the seed's tags |
| Multi-seed similarity | `find_similar_multi()` — union of the seeds' tags |
| Model outputs / tags | `model_tags()` — Jamendo `musicinfo`（genre / mood / instruments / speed / vocals）|

The catalog `backend/data/demo_catalog.json` (2,401 tracks) is harvested once from the public
Jamendo API by [`backend/build_catalog.py`](backend/build_catalog.py); only that build step needs
`JAMENDO_CLIENT_ID`. Audio is served to the browser straight from Jamendo's public CDN, no key
involved.

**This is term matching, not audio-semantic search** — the honest ceiling of what public data
allows. To restore real semantic retrieval, the next step is a local caption-vector index built
from [JamendoMaxCaps](https://huggingface.co/datasets/amaai-lab/JamendoMaxCaps)'
`final_caption30sec.jsonl` (CC BY-SA 3.0, keyed by Jamendo track id); `catalog.py`'s public
interface would not need to change.

## 🧹 Maintenance

Do not commit local runtime state:

| Path | Why |
|---|---|
| `.env` | Local API keys (the demo itself needs none) |
| `backend/.venv/` | Local Python environment |
| `frontend/node_modules/` | Local npm install |
| `backend/memory/*.md` | Runtime user memory |
| Build caches | Generated artifacts |

Recommended pre-commit checks:

```bash
cd backend && uv run pytest
cd ../frontend && npm run build
git status --short
```

---

## Terms and licenses

- Challenge brief: [`CHALLENGE.md`](CHALLENGE.md)
- Challenge agreement: [`CHALLENGE_AGREEMENT.md`](CHALLENGE_AGREEMENT.md)
- Code and docs: MIT, see [`LICENSE`](LICENSE)
- Data pack terms: [`DATA_LICENSE.md`](DATA_LICENSE.md)

<div align="center">

Built by the original team at **[HACKATUNE 2026](https://munichmusiclabs.com/events/hackatune-2026/)**
(Munich Music Labs × Cyanite) · continued here

</div>
