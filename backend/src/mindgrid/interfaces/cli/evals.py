"""`mindgrid eval run`: score a golden-set file against a project (operator tool; runs
with superadmin rights, like the other admin commands)."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from mindgrid.core.errors import ApiError
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.evals import judge, runner
from mindgrid.platform.jobs import handlers

app = typer.Typer(no_args_is_help=True, help="Retrieval evals.")


async def _run(
    project: uuid.UUID, golden: runner.GoldenSet, judge_mode: judge.JudgeMode | None
) -> dict[str, object]:
    operator = Actor(None, superadmin=True)
    try:
        async with transaction(operator) as tx:
            done = await runner.run(tx, project, golden)
        out: dict[str, object] = {
            "run_id": str(done.id),
            "metrics": done.metrics,
            "setup": done.setup,
            "misses": [c for c in done.cases if c["hit"] < 1],
        }
        if judge_mode:
            graded = await judge.judge_run(operator, done.id, judge_mode)
            out["judge"] = {"by": graded.judge, "answerer": graded.answerer, **graded.metrics}
        return out
    finally:
        await db_engine.dispose()


@app.command("run")
def run(
    project: Annotated[uuid.UUID, typer.Option(help="Project id.")],
    file: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Golden set (JSON).")],
    judge_mode: Annotated[
        str | None, typer.Option("--judge", help="Also grade with an LLM: gemini or local.")
    ] = None,
) -> None:
    """Print the metrics as JSON and store the run (misses are listed for review)."""
    if judge_mode not in (None, "gemini", "local"):
        typer.echo("error: --judge must be gemini or local", err=True)
        raise typer.Exit(2)
    try:
        golden = runner.GoldenSet.model_validate_json(file.read_bytes())
        result = asyncio.run(_run(project, golden, judge_mode))  # type: ignore[arg-type]
    except (ValidationError, ApiError, handlers.PermanentJobError) as err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(1) from None
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
