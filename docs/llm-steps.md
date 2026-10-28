# Optional LLM steps around retrieval

Retrieval never needs an LLM: embeddings, keyword and trigram search, the reranker and the
cutoffs all run without one. Three steps can use one when switched on. Each has its own
setting (UI: project → *Settings*), off by default, and uses the same writers as
server-side answers: `gemini` (the project's Gemini key, secret `provider.gemini.api_key`)
or `local` (the Ollama server in `MINDGRID_LLM_LOCAL_URL`). A failing or slow model never
breaks the step it helps: it is skipped and the reason is recorded.

| Step | Setting (scopes) | What it does | If the model fails |
|--|--|--|--|
| Contextual retrieval | `index.contextualize` (system, project, category) | Before a chunk is embedded, the model writes one or two sentences placing it in its document (title, outline, the text around it). The line is searched by meaning and by keyword; readers still see the original passage. | The remaining chunks are indexed without a line; the document stays searchable. |
| Query rewrite | `recall.rewrite` (system, project) | The question is also turned into a search query (exact names and numbers kept, likely terms added). Both are searched and fused; the reranker still scores every passage against the original question, so a rewrite can add passages but not push a good one out. | Skipped after `MINDGRID_RECALL_REWRITE_SECONDS` (20); `skipped.rewrite` says why. |
| LLM judge for evals | per run: `"judge": "local"` or `"gemini"` (API, UI *Evals*, `mindgrid eval run --judge`) | Every on-topic case is graded: do the passages hold what the question needs (context: yes 1 / partly 0.5 / no 0), and, when the project writes answers (`answer.llm`), how much of the answer the passages support (faithfulness 0–1). Stored next to the run; API runs grade in the background and emit `eval.judged`. | A case the judge cannot grade is counted in `failed`. |

## Cost and when to switch them on

- Contextual retrieval costs one model call per new or changed chunk. A chunk whose text
  did not change keeps its line and its vector (carried over to the new version), so
  re-uploading a document only pays for what changed. Switching the setting off removes the
  lines at the next indexing of each document.
- Query rewrite adds one model call per question (seconds on a local model). It helps
  short or vague questions and questions in a different language from the documents.
- The judge should be a stronger model than the one answering; its scores are a second
  opinion next to the retrieval metrics, which need no model at all.

Measure before keeping a step on: run the same golden set with the step off and on
(*Evals*), and compare hit@k, MRR and abstention.
