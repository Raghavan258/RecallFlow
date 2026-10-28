# Retrieval

Phase 2 ranks memories that are already stored. It does not generate an answer and it does not replace the Phase 1 extractor.

`POST /api/conversations/{id}/retrieve` takes `question`, `mode` (`keyword`, `graph`, or `budget`), `token_budget`, and `limit`. The response lists memories, topic labels, source messages, scores, explanations, token usage, and latency.

`limit` is the maximum number of ranked candidates considered. It does not promise that many selected memories. In `budget` mode a candidate that does not fit is discarded whole, a later candidate that fits can still be kept, and nothing ranked past `limit` is pulled in to fill the budget.

The budget tokenizer counts whitespace-separated tokens, including the `Sources:` line. A negative budget is rejected. Zero keeps nothing. Keyword and graph modes do not discard for the budget; they still report the token count of the returned package.

## Modes

- `keyword` ranks memories by the fraction of question terms that appear in the memory text.
- `graph` starts from those memories and adds neighbors of those seeds only. If a seed says "depends on" a phrase of at least two content words, memories that contain that whole phrase are included even when the extractor stored no edge. Seed explanations keep the shared terms. A neighbor explanation names the stored link. When both ends of a correction are candidates, each explanation names the other memory. It follows `SUPERSEDES`, `CONTRADICTS`, and `SUPPORTS` between memories, and `DEPENDS_ON` from a topic toward the topic it depends on. It does not walk `RELATED_TO` or `MENTIONS`, and it does not follow a chain past the first hop. After scoring, it keeps the 12 highest-scoring candidates. The edge bonus is added only to neighbors, so a neighbor with no shared terms stays below every memory that shares a question term.
- `budget` uses the graph ranking, then packs evidence until the token budget is full. The correction bonus is added only when both ends of a `SUPERSEDES` or `CONTRADICTS` edge are candidates. Equal scores are ordered by memory id.
- Evaluation-only labels `keyword_budget` and `graph_budget` apply that same packer to the keyword and graph rankings. They are not API modes. `graph_budget` is the evaluation name for the API `budget` mode.

## Datasets

The synthetic conversation is `backend/app/datasets/data/synthetic_conversation.json`. Questions, answers, evidence ids, and topic keywords are in `synthetic_eval.json`. Retrieval never receives that file.

LoCoMo (snap-research/locomo) is CC BY-NC 4.0. LongMemEval chat data is published by its authors (MIT repository; download the cleaned JSON yourself from the Hugging Face `xiaowu0162/longmemeval-cleaned` files). RecallFlow does not vendor either dataset. `app.datasets.adapters` converts a file you already have into an import payload and a separate question list. Generated LoCoMo observations and session summaries are not imported as messages.

## Evaluation

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.retrieval.evaluate
```

The command prints two labeled sections. `unconstrained` is keyword and graph with no token cap (`token_budget` is null and nothing is discarded). `fixed_budget` runs at 20, 40, and 80 tokens for `keyword_budget`, `graph_budget`, and API `budget`, all with the same whole-memory packer and limit 5. Ten synthetic questions are scored: three single-topic, and two each of temporal update, multi-hop, distractor, and unanswerable.

Recall@5 is the fraction of labeled original source ids present on the selected memories inside that limit-5 window. It is not answer accuracy. Unanswerable questions have no gold ids, so recall is left blank. Extraction coverage is the fraction of those gold ids that the extractor stored on any memory. Conditional retrieval recall uses only the gold ids that were stored, so a missed extraction is not counted as a retrieval miss. On this run, coverage was 1.0 for every answerable question, so conditional recall matched Recall@5.

Topic-keyword contamination is the share of selected memories whose topic labels contain none of the question's labeled keywords. It is a heuristic, not a gold judgment. False-retrieval rate is the share of selected memories that carry none of the gold source ids. An empty unanswerable result has rate 0. Latency in the command output is one process-local measurement and is not a benchmark.

Unconstrained baselines from one local run:

| Mode | Category | n | Recall@5 | Topic-keyword contamination | False retrieval | Tokens |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | single_topic | 3 | 1.0 | 0.0 | 0.1111 | 25.6667 |
| keyword | temporal_update | 2 | 1.0 | 0.0 | 0.5 | 42.0 |
| keyword | multi_hop | 2 | 0.75 | 0.0 | 0.5 | 33.5 |
| keyword | distractor | 2 | 1.0 | 0.0 | 0.0 | 22.0 |
| keyword | unanswerable | 2 | n/a | 0.0 | 0.0 | 0.0 |
| graph | single_topic | 3 | 1.0 | 0.0 | 0.1111 | 25.6667 |
| graph | temporal_update | 2 | 1.0 | 0.0 | 0.5 | 42.0 |
| graph | multi_hop | 2 | 1.0 | 0.0 | 0.5 | 45.0 |
| graph | distractor | 2 | 1.0 | 0.0 | 0.0 | 22.0 |
| graph | unanswerable | 2 | n/a | 0.0 | 0.0 | 0.0 |

Fixed-budget Recall@5 and selected tokens. `graph_budget` matched API `budget` on every row in this run, so the table lists `budget` once for that pair.

| Budget | Mode | single_topic | temporal | multi_hop | distractor | unanswerable tokens |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | keyword_budget | 0.6667 / 13.3333 | 1.0 / 18.0 | 0.5 / 11.0 | 0.5 / 11.0 | 0.0 |
| 20 | budget | 0.6667 / 13.3333 | 1.0 / 18.0 | 0.5 / 11.0 | 0.5 / 11.0 | 0.0 |
| 40 | keyword_budget | 1.0 / 25.6667 | 1.0 / 30.0 | 0.75 / 28.0 | 1.0 / 22.0 | 0.0 |
| 40 | budget | 1.0 / 25.6667 | 1.0 / 30.0 | 1.0 / 33.0 | 1.0 / 22.0 | 0.0 |
| 80 | keyword_budget | 1.0 / 25.6667 | 1.0 / 42.0 | 0.75 / 33.5 | 1.0 / 22.0 | 0.0 |
| 80 | budget | 1.0 / 25.6667 | 1.0 / 42.0 | 1.0 / 45.0 | 1.0 / 22.0 | 0.0 |

On this sample, at 40 and 80 tokens, graph packing kept multi-hop Recall@5 at 1.0 while keyword packing stayed at 0.75. At 20 tokens the three packed modes matched, and multi-hop recall fell to 0.5. These numbers are not a claim about LoCoMo or LongMemEval.

## Limits

Retrieval only sees memories the extractor stored. A paraphrase with no shared content word is missed unless it is a direct neighbor of a lexical seed and fewer than K seeds already fill the result. `DEPENDS_ON` is followed in one direction and only one hop. The whitespace tokenizer is not a model tokenizer. False-retrieval rate counts extra memories that do not carry a gold source id; it does not by itself mean the memory is off topic. Answer accuracy is not measured because this phase does not generate answers.
