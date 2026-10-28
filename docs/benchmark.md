# Retrieval benchmark

`benchmark-v1` is a synthetic studio-operations transcript. It is not a public benchmark and it does not estimate real-world performance.

## Construction

The conversation is `backend/app/datasets/data/benchmark_conversation.json` (44 messages). The questions are `benchmark_questions.json` (63 questions). Each answerable question lists `evidence_source_ids`: the messages that state the fact. Those labels were written from the transcript. They were not copied from a retrieval run.

A memory is relevant when one of its source ids is in that list. Extractor keys look like `memory:12`. The report's `memory_index` maps each source id to those keys by reading the baseline extraction, not by reading rank order. Unanswerable questions have an empty list because the transcript does not contain the fact. Some of them still share a word such as "studio" with unrelated messages, so an empty result is not guaranteed.

Splits are fixed on each question: 41 development questions (33 answerable) and 22 held-out questions (19 answerable). The development split was used to choose the change below. The held-out split was not.

## How to run

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.retrieval.benchmark
```

That writes `backend/app/datasets/data/benchmark_report.json`. `benchmark_report_before.json` is the same run before the dependency-phrase change. The command calls the baseline extractor and the retrieval engine. It does not call an external model.

Settings for the mode comparison: limit 10 and token budget 80. Keyword and graph do not discard to meet the budget. Budget mode does. The same budget mode is also scored at 20, 40, and 80 tokens. The tokenizer is the project tokenizer: a whitespace split of the memory text plus the `Sources:` line.

The `dev` and `heldout` fields group this report. Retrieval receives the question text, mode, limit, and token budget. It does not receive the split, and no retrieval module other than this scorer mentions `heldout`.

## Metrics

Recall@k, for one answerable question, is the fraction of its authored source ids that appear on the first k selected memories. The reported Recall@k is the mean of those fractions. The denominator is the answerable count, not the full question count. Unanswerable questions have no source ids, so their recall is left out.

MRR is the mean of `1 / rank` over answerable questions. Rank is the 1-based position of the first selected memory that carries any authored source id. A miss contributes 0. Unanswerable questions are not in the MRR denominator.

Empty-result rate is the share of questions in that group with no selected memory. For unanswerable questions, empty is the expected outcome. For answerable questions, empty is a miss.

Latency is one `time.perf_counter` interval around a single `retrieve` call, in milliseconds. The sample count is the number of questions in the split. It is not a repeated benchmark.

Budget violations count budget-mode questions whose selected token total exceeds the budget being scored. The count was 0 at 20, 40, and 80 tokens.

Recall@5 and Recall@10 were equal on every row. Gold that was found was already inside the first five selected memories.

## Results before the change

Development, 33 answerable questions:

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Mean tokens | Unanswerable empty |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.3485 | 0.7424 | 0.7424 | 0.6515 | 35.3171 | 0.75 |
| graph | 0.3485 | 0.7424 | 0.7424 | 0.6515 | 37.878 | 0.75 |
| budget | 0.3485 | 0.7424 | 0.7424 | 0.6515 | 34.8049 | 0.75 |

Held-out, 19 answerable questions:

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Mean tokens | Unanswerable empty |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.3947 | 0.7632 | 0.7632 | 0.7456 | 29.8636 | 1.0 |
| graph | 0.3684 | 0.7895 | 0.7895 | 0.7193 | 36.1818 | 1.0 |
| budget | 0.3684 | 0.7895 | 0.7895 | 0.7193 | 34.4091 | 1.0 |

On the development split, direct and related questions reached Recall@5 of 1.0. Paraphrase Recall@5 was 0.0625, and 7 of 8 paraphrase questions returned nothing, because the questions do not share content words with the fact. Graph traversal did not change that. Dependency Recall@5 was 0.6667 for every mode: the "depends on" sentence was found, and the fact it names was missed when the question did not repeat that fact's words. The extractor had not stored a `DEPENDS_ON` edge for those development questions, because the named phrases were not selected as topics.

## Change

Graph and budget mode now read an explicit "depends on" phrase in a lexical seed. If the text after "depends on" has at least two content words, memories that contain all of those words are added. Keyword mode is unchanged. No embeddings or model calls were added.

## Results after the change

Development:

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Mean tokens | Unanswerable empty |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.3485 | 0.7424 | 0.7424 | 0.6515 | 35.3171 | 0.75 |
| graph | 0.3485 | 0.7727 | 0.7727 | 0.6515 | 40.1463 | 0.75 |
| budget | 0.3485 | 0.7727 | 0.7727 | 0.6515 | 37.0732 | 0.75 |

Development dependency Recall@5 for graph and budget moved from 0.6667 to 1.0. Direct recall stayed 1.0. Paraphrase recall stayed 0.0625. The unanswerable empty rate stayed 0.75. MRR did not change, because the added memories were not the first result.

Held-out graph and budget Recall@5 stayed 0.7895, and held-out MRR stayed 0.7193. Held-out dependency recall was already 1.0, because that question had a stored `DEPENDS_ON` edge. Held-out graph mean tokens rose from 36.1818 to 37.3182, and budget mean tokens rose from 34.4091 to 34.9545. Keyword did not change on either split. The held-out overall recall was not used to choose or revise the change.

## Budget trade-off

Budget mode uses the graph ranking, then keeps whole memories until the token budget is full. These are the same questions and limit 10. Mean tokens are the mean selected-token count over every question in the split, including empty results. Answerable Recall@5 uses the answerable denominator.

Development, 33 answerable questions:

| Budget | Recall@5 | MRR | Mean tokens | Answerable empty |
| --- | --- | --- | --- | --- |
| 20 | 0.3939 | 0.5909 | 10.5122 | 0.2121 |
| 40 | 0.697 | 0.6515 | 22.5366 | 0.2121 |
| 80 | 0.7727 | 0.6515 | 37.0732 | 0.2121 |

At 20 tokens, direct Recall@5 is 0.3077 and dependency Recall@5 is 0.6667. At 40 tokens those are 0.8846 and 0.8333. At 80 tokens both are 1.0. Paraphrase Recall@5 stays 0.0625 at every budget, so the cap is not what drops those questions. MRR is lower at 20 tokens because a top-ranked memory can be too large to keep. There were no budget violations.

Held-out, 19 answerable questions, reported and not used to change the ranker:

| Budget | Recall@5 | MRR | Mean tokens | Answerable empty |
| --- | --- | --- | --- | --- |
| 20 | 0.3684 | 0.6316 | 9.6364 | 0.1579 |
| 40 | 0.7368 | 0.7193 | 23.6818 | 0.1579 |
| 80 | 0.7895 | 0.7193 | 34.9545 | 0.1579 |

## Why paraphrases fail

Keyword score is the fraction of question content tokens that appear in a memory. A memory with no shared content token scores 0 and is not a seed. Graph and budget expansion start from seeds, so they cannot recover a fact that shares nothing with the question.

Of the 13 paraphrase questions, 10 share no content token with their gold messages. The other three share one incidental word: `month` (`rent-para`), `beginner` (`raku-para`), and `desk` (`volunteer-para`). Examples with no overlap: "How hot is the pottery oven after the revision?" against the kiln-temperature messages, and "How many sacks were requested after the correction?" against the clay-order messages. The report field `paraphrase_overlap` lists the query tokens and shared tokens for each of the 13.

A later semantic retriever should be compared with this lexical baseline on these same question ids. That comparison is not part of this run.

## Limits

Paraphrases with no shared content word are still missed, as measured above. Recall@1 is low on two-message facts because one memory usually carries one source id, so a single top hit cannot cover both ids. The whitespace tokenizer is not a model tokenizer. These numbers describe this synthetic set only.
