# RecallFlow architecture

RecallFlow turns a conversation into a graph of topics, memories, entities, and explicit relationships. Phase 1 stores the graph and lets a person explore it. It does not answer questions or rank memories for retrieval.

## Flow

1. Import a pasted transcript or a JSON conversation.
2. Store every original message with speaker, order, content, and only the source id or timestamp that was actually provided. Provided timestamps are converted to UTC before they are stored.
3. Run an extraction provider.
4. Validate the provider output.
5. Append an extraction run, topics, memories, entities, and relationships.
6. Project the latest run into a graph for the dashboard.

Graph construction reads stored records. It does not call the extractor and does not add edges that were not stored.

## Packages

- `frontend/` is a Vite + React + TypeScript app. React Flow renders the graph. The dev server proxies `/api` and `/health` to the API.
- `backend/app/` is a FastAPI application.
- `backend/app/extraction/` selects topics and memories. `BaselineExtractor` is deterministic and needs no API key. `LlmExtractor` is optional and reads `LLM_API_KEY` from the environment.
- `backend/app/graph/builder.py` is a pure projection from in-memory records to nodes and edges.
- `backend/tests/` covers import order, extraction, graph edges, provenance, validation failures, and persistence.

## Data model

SQLite is the local database. Models use portable SQLAlchemy types (`String`, `Text`, `DateTime`, `JSON`, integer foreign keys as strings) so a later PostgreSQL database can use the same tables with a driver such as `postgresql+psycopg`.

Original messages live in `messages`. Extracted statements live in `memories` and point back through `memory_sources`. A memory can link to several topics through `memory_topics`. Relationships live in `graph_relationships`.

Re-running extraction inserts a new `extraction_runs` row and new child rows. Older decisions stay in the database. The API reads the latest run for a conversation. Conflicting statements in one run are both stored. A `CONTRADICTS` or `SUPERSEDES` edge is added only when the later sentence has an explicit cue (`actually`, `no longer`, `contradicts`, or `supersedes`) and at least two shared content words with an earlier memory in the same conversation. One shared generic word is not enough, and the earlier statement is kept.

## Timestamps

Message timestamps and `created_at` in API responses, plus graph message payloads, are ISO-8601 UTC with a `Z` suffix, for example `2026-03-02T09:30:00Z`. A missing timestamp is JSON `null`. An offset such as `+05:30` is converted to the same instant in UTC before insert. Naive stored values are read back as UTC. This is an application convention; the `messages.timestamp` column is unchanged and no migration is required. Importing the same transcript again creates a new conversation.

## Baseline extractor limits

The baseline provider counts repeated keywords, classifies sentences with cue phrases, and creates a relationship only when a shared record or an explicit cue supports it. It misses paraphrases, pronouns, and sarcasm. Those limits are returned on the graph payload and shown in the UI. The optional LLM provider can return the same JSON shape; its output is validated before it is saved.

## API

Interactive docs are served at `http://127.0.0.1:8000/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| POST | `/api/conversations/import` | Store a transcript or JSON messages |
| GET | `/api/conversations` | List conversations and counts |
| GET | `/api/conversations/{id}` | Original messages in order |
| POST | `/api/conversations/{id}/extract` | Append an extraction run and return its graph |
| GET | `/api/conversations/{id}/graph` | Latest graph, or an empty graph before extraction |
| GET | `/api/memories/{id}` | Memory, topics, relationships, and source messages |
| GET | `/api/topics` | Topics, optionally filtered by `conversation_id` |
| POST | `/api/conversations/{id}/retrieve` | Rank stored memories for a question |
| GET | `/api/sample/conversation` | Bundled Nimbus launch sample |

## Retrieval

`POST /api/conversations/{id}/retrieve` ranks memories from the latest extraction run. Keyword mode uses term overlap. Graph mode adds one hop from the lexical seeds along stored `SUPPORTS`, `CONTRADICTS`, `SUPERSEDES`, and `DEPENDS_ON` edges, then keeps the highest-scoring candidates. Budget mode packs that ranking under a whitespace token limit. `limit` is how many ranked candidates are considered, and discarded candidates are not replaced from further down the list. The response is evidence and source messages, not an answer. Details and the synthetic comparison are in `docs/retrieval.md`.

## Graph interaction

The first view shows root topic nodes. Expanding a topic reveals subtopics, memories, decisions, and entities linked to it. A parent-topic filter also includes memories that belong only to a descendant topic. Source message nodes stay hidden until a memory's evidence action asks for them, and those requested messages stay visible even when the search text does not match them. Search can reveal a collapsed node directly. The layout does not invent edges to pull isolated nodes together.
