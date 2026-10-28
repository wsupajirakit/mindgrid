"""Run events: one when a run ends, with its outcome and links (outputs stay on the run)."""

from mindgrid.platform.events import types


class RunFinished(types.EventData):
    run_id: str
    playbook_id: str
    playbook_version: int
    playbook_status: str
    status: str
    error: str
    outputs: list[str]  # output names; read them through links.api
    links: types.Links


RUN_COMPLETED = types.define("run.completed", "A playbook run finished.", RunFinished)
RUN_FAILED = types.define("run.failed", "A playbook run stopped on a failing step.", RunFinished)
OUTCOMES = [RUN_COMPLETED.name, RUN_FAILED.name, "job.failed"]
