"""`mindgrid` command line. The first superadmin is created here, never over HTTP."""

import asyncio
import getpass
import sys

import typer
from sqlalchemy import func, select

from mindgrid.core import brand
from mindgrid.core.errors import ApiError
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import SystemRole, User

from . import evals, remote, worker

app = typer.Typer(no_args_is_help=True, help="Command line for the engine.")
admin = typer.Typer(no_args_is_help=True, help="Operator tasks.")
app.add_typer(admin, name="admin")
app.add_typer(worker.app, name="worker")
app.add_typer(evals.app, name="eval")
remote.register(app)


@app.command("mcp")
def mcp_stdio() -> None:
    """Serve the knowledge tools over MCP (stdio) with the client profile's API key."""
    from mindgrid.interfaces.mcp_server import server  # noqa: PLC0415 — only this command

    server.build().run("stdio")


@app.callback()
def _banner(ctx: typer.Context) -> None:
    ctx.obj = brand.get_settings().name


async def _create_superadmin(email: str, name: str, password: str) -> str:
    try:
        async with transaction(Actor(user_id=None, superadmin=True)) as tx:
            user = await users.create_user(
                tx,
                email=email,
                display_name=name,
                password=password,
                system_role=SystemRole.SUPERADMIN,
            )
            return str(user.id)
    finally:
        await db_engine.dispose()


async def _reindex(email: str) -> int:
    from mindgrid.knowledge.index import service as indexing  # noqa: PLC0415 — this command only
    from mindgrid.knowledge.library.models import Document, DocumentVersion  # noqa: PLC0415

    try:
        async with transaction(Actor(None, superadmin=True)) as tx:
            user = await tx.scalar(select(User).where(func.lower(User.email) == email.lower()))
            if user is None or user.system_role is not SystemRole.SUPERADMIN:
                raise typer.BadParameter(
                    "give the email of a superadmin (jobs run as that account)"
                )
            uid = user.id
        async with transaction(Actor(uid, superadmin=True)) as tx:
            current = (
                select(DocumentVersion)
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(DocumentVersion.version == Document.current_version)
            )
            versions = list((await tx.scalars(current)).all())
            for version in versions:
                await indexing.enqueue(tx, version)
            return len(versions)
    finally:
        await db_engine.dispose()


@admin.command("ensure-app-role")
def ensure_app_role() -> None:
    """Create the database role the API and workers log in as (or align its password with
    MINDGRID_DATABASE_URL). Runs as the owner (MINDGRID_MIGRATION_DATABASE_URL), before
    migrations; safe to repeat."""
    from mindgrid.db import app_role  # noqa: PLC0415 — this command only

    typer.echo(f"app role {asyncio.run(app_role.ensure())}")


@admin.command("reindex")
def reindex(email: str = typer.Option(..., help="Superadmin account the jobs run as.")) -> None:
    """Queue indexing of every current document version (after changing the embedding model;
    vectors of the old model stay in their own space until removed)."""
    typer.echo(f"queued: {asyncio.run(_reindex(email))} document version(s); run the worker")


@admin.command("create-superadmin")
def create_superadmin(
    email: str = typer.Option(..., help="Sign-in email."),
    name: str = typer.Option("", help="Display name."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the password from standard input (automation)."
    ),
) -> None:
    """Create a superadmin account. The password is asked for, or read from standard input
    with --password-stdin; it is never an argument."""
    if password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            raise typer.BadParameter("passwords differ")
    try:
        user_id = asyncio.run(_create_superadmin(email, name, password))
    except ApiError as err:
        typer.echo(f"error: {err.code}: {err.message}", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"superadmin created: {user_id}")
