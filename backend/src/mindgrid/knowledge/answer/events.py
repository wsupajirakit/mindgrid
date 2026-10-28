"""Answer events (server-written answers; the text stays in the response)."""

from mindgrid.platform.events import types


class AnswerCompleted(types.EventData):
    answer_id: str
    mode: str
    writer: str
    passages: int
    citations_ok: bool | None
    links: types.Links


ANSWER_COMPLETED = types.define(
    "answer.completed", "A server-written answer is ready.", AnswerCompleted
)
