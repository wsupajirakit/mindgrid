"""Eval events."""

from mindgrid.platform.events import types


class EvalCompleted(types.EventData):
    eval_run_id: str
    name: str
    k: int
    metrics: dict[str, float]
    links: types.Links


EVAL_COMPLETED = types.define("eval.completed", "A retrieval eval run finished.", EvalCompleted)


class EvalJudged(types.EventData):
    eval_run_id: str
    judge: str
    metrics: dict[str, float]
    links: types.Links


EVAL_JUDGED = types.define(
    "eval.judged", "An LLM finished grading an eval run (context and faithfulness).", EvalJudged
)
