"""`mindgrid worker`: run background jobs (indexing, runs, syncs, Synapse, eval judging)."""

import asyncio
import signal

import typer

from mindgrid.bridges.connectors import service as connectors
from mindgrid.db import engine as db_engine
from mindgrid.knowledge.evals import judge as eval_judge
from mindgrid.knowledge.evals import log as recall_log
from mindgrid.knowledge.index import service as indexing
from mindgrid.platform.events import deliver as event_delivery
from mindgrid.platform.jobs import worker as jobs
from mindgrid.runs import service as runs
from mindgrid.synapse import service as synapse

app = typer.Typer(no_args_is_help=True, help="Background jobs.")
# Importing a feature module registers its job kinds and periodic tasks.
JOB_KINDS = (indexing.KIND, runs.KIND, connectors.KIND, synapse.KIND, eval_judge.KIND)
PERIODIC = (recall_log.purge, event_delivery.run_once)


async def _forever() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await jobs.run_forever(jobs.worker_name(), stop)
    finally:
        await db_engine.dispose()


async def _drain() -> int:
    try:
        return await jobs.run_until_empty(jobs.worker_name())
    finally:
        await db_engine.dispose()


@app.command("run")
def run(once: bool = typer.Option(False, "--once", help="Stop when the queue is empty.")) -> None:
    """Process jobs until stopped (Ctrl-C / SIGTERM finishes the current job first)."""
    if once:
        typer.echo(f"jobs processed: {asyncio.run(_drain())}")
        return
    asyncio.run(_forever())
