# RecallFlow

RecallFlow turns a conversation into a source-linked memory graph, then retrieves a compact evidence package for a question. It does not write an answer. Every returned memory points back to the original message.

The local extractor needs no API key. Keyword, graph, and token-budget retrieval share one engine, so the three modes can be compared on the same questions.

## What a reader can verify

- Import keeps the original messages. Extraction writes a separate run of topics, memories, entities, and relationships.
- Retrieval returns memory ids, topic labels, source messages, scores, explanations, token counts, and latency.
- Graph mode walks one hop from lexical seeds. It follows `SUPPORTS`, `SUPERSEDES`, `CONTRADICTS`, and directional `DEPENDS_ON`. It also follows an explicit "depends on" phrase when the extractor stored no edge.
- Budget mode packs whole memories with the project's whitespace tokenizer and never truncates a memory to fit.
- The held-out split is used only to report scores. Retrieval code does not read it.
- Labels were written from the transcript. They were not copied from a retrieval run.

There is no vector index and no answer-generation model in this version. Paraphrases with no shared content word are still missed. That gap is measured below.

## Measured retrieval

`benchmark-v1` is a synthetic studio transcript: 44 messages and 63 questions (41 development, 22 held out). 33 development questions and 19 held-out questions have authored source ids. Recall and MRR use those answerable questions as the denominator. Unanswerable questions are scored by whether the result is empty.

Limit is 10. The mode table uses an 80-token budget. Budget mode is also scored at 20, 40, and 80. Numbers are from one local run of `python -m app.retrieval.benchmark`. They describe this synthetic set only. Definitions and the machine-readable report are in [docs/benchmark.md](docs/benchmark.md).

### Development, after the dependency-phrase change

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Mean tokens | Unanswerable empty |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.3485 | 0.7424 | 0.7424 | 0.6515 | 35.3171 | 0.75 |
| graph | 0.3485 | 0.7727 | 0.7727 | 0.6515 | 40.1463 | 0.75 |
| budget | 0.3485 | 0.7727 | 0.7727 | 0.6515 | 37.0732 | 0.75 |

Before that change, development graph and budget Recall@5 were 0.7424, the same as keyword. Dependency Recall@5 moved from 0.6667 to 1.0. Direct Recall@5 stayed 1.0. Paraphrase Recall@5 stayed 0.0625. MRR did not move, because the added memories were not the first hit.

### Held-out, unchanged by that change

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Mean tokens | Unanswerable empty |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.3947 | 0.7632 | 0.7632 | 0.7456 | 29.8636 | 1.0 |
| graph | 0.3684 | 0.7895 | 0.7895 | 0.7193 | 37.3182 | 1.0 |
| budget | 0.3684 | 0.7895 | 0.7895 | 0.7193 | 34.9545 | 1.0 |

Held-out Recall@5 and MRR match the run from before the change. Held-out graph mean tokens rose from 36.1818 to 37.3182, and budget mean tokens rose from 34.4091 to 34.9545.

### Budget mode trade-off

Whole memories are kept until the budget is full. No run exceeded its budget.

| Split | 20 tokens | 40 tokens | 80 tokens |
| --- | --- | --- | --- |
| Development Recall@5 | 0.3939 | 0.697 | 0.7727 |
| Development MRR | 0.5909 | 0.6515 | 0.6515 |
| Development mean tokens | 10.5122 | 22.5366 | 37.0732 |
| Held-out Recall@5 | 0.3684 | 0.7368 | 0.7895 |
| Held-out MRR | 0.6316 | 0.7193 | 0.7193 |
| Held-out mean tokens | 9.6364 | 23.6818 | 34.9545 |

At 20 tokens, development direct Recall@5 is 0.3077 and dependency Recall@5 is 0.6667. At 80 tokens both are 1.0. Paraphrase Recall@5 stays 0.0625 at every budget.

### Why paraphrases miss

A memory becomes a seed only when it shares a content token with the question. Graph expansion starts from those seeds, so a fact with no shared token is never reached.

Ten of 13 paraphrase questions share no content token with the gold messages. "How hot is the pottery oven after the revision?" does not overlap the kiln-temperature messages. The other three share one incidental word: `month`, `beginner`, or `desk`. A later semantic retriever should be compared with this lexical baseline on the same question ids.

Recall@1 looks low on two-message facts because one memory usually carries one source id. A single top hit cannot cover both ids. Recall@5 and Recall@10 were equal: gold that was found was already inside the first five selected memories.

## Layout

```text
backend/app/extraction/     cue-based topics, memories, entities, relationships
backend/app/retrieval/      keyword, one-hop graph, token packing, benchmark
backend/app/datasets/       synthetic set and benchmark-v1 labels
backend/app/services/       import, extraction runs, graph reads, retrieval API
backend/tests/              extractor, API, retrieval, and benchmark checks
frontend/src/               React workspace: import, graph, evidence, retrieval
docs/                       architecture, retrieval design, benchmark definitions
```

The API is FastAPI and SQLite. The UI is React, TypeScript, and Vite. The graph is rendered with React Flow. Latest checks in this workspace: backend `ruff` clean and 47 pytest tests passed. Frontend lint, Vitest, and production build passed on the last UI change.

## Setup

Windows PowerShell, from the repository root:

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
Copy-Item .env.example .env
```

`EXTRACTION_PROVIDER=baseline` is the default. Leave `LLM_API_KEY` empty. Set `EXTRACTION_PROVIDER=llm` only when a key is available. The optional provider calls an OpenAI-compatible chat-completions endpoint. Keys stay in the environment.

## Run

Two terminals:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. API docs are at `http://127.0.0.1:8000/docs`. Vite proxies `/api` and `/health` to port 8000. `.\start.ps1` starts both after dependencies are installed. If script execution is blocked, set the process execution policy to `Bypass` for that window only.

In the dashboard, **Load sample** imports the bundled Nimbus launch conversation and extracts the graph. Ask a question in **Retrieve** to rank memories and open their source messages on the graph.

Paste format:

```text
Ava [2026-03-02T15:00:00Z]: Let's plan the launch.
Ben: The privacy review depends on onboarding.
```

Lines without a speaker continue the previous message. A URL or a clock time continues the previous message. Missing timestamps stay missing. Provided timestamps are stored as UTC.

## Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m app.retrieval.benchmark
```

```powershell
cd frontend
npm run lint
npm test
npm run build
```

## Further reading

- [docs/architecture.md](docs/architecture.md) for the data model and API
- [docs/retrieval.md](docs/retrieval.md) for ranking and packing
- [docs/benchmark.md](docs/benchmark.md) for metric definitions and the before/after tables
