"""The app role, made by the migration step (as the database owner) instead of an init
script: hosting panels do not always keep repository files next to the database, and an
init script runs only on the very first start. Its name and password come from the app's
own connection URL, so the two can never disagree; a changed password is applied on the
next deployment. The role logs in, owns nothing and is never superuser or BYPASSRLS."""

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from . import config as db_config

_EXISTS = text("select exists (select from pg_roles where rolname = :role)")
# format() quotes the name (%I) and the password (%L) on the server; the statement it
# returns is run as-is, so no character of the password can change its meaning.
_CREATE = text(
    "select format('create role %I login nosuperuser nobypassrls nocreatedb nocreaterole"
    " noreplication password %L', cast(:role as text), cast(:pw as text))"
)
_ALTER = text(
    "select format('alter role %I login nosuperuser nobypassrls nocreatedb nocreaterole"
    " noreplication password %L', cast(:role as text), cast(:pw as text))"
)
_GRANTS = text(
    "select format('grant connect on database %I to %I', current_database(), cast(:role as text)),"
    " format('grant usage on schema public to %I', cast(:role as text))"
)


def _role_and_password() -> tuple[str, str]:
    url = make_url(db_config.app_url())
    role = db_config.get_settings().app_role
    if url.username != role:
        raise RuntimeError(f"MINDGRID_DATABASE_URL must log in as {role}, the app role")
    if not url.password:
        raise RuntimeError("MINDGRID_DATABASE_URL has no password for the app role")
    return role, str(url.password)


async def ensure() -> str:
    """Create the app role, or bring its password and limits in line. Returns what it did."""
    role, password = _role_and_password()
    owner = db_config.get_settings().migration_url
    if owner is None:
        raise RuntimeError("MINDGRID_MIGRATION_DATABASE_URL is not set (the owner connection)")
    engine = create_async_engine(owner.get_secret_value())
    try:
        async with engine.begin() as conn:
            existed = bool(await conn.scalar(_EXISTS, {"role": role}))
            statement = await conn.scalar(
                _ALTER if existed else _CREATE, {"role": role, "pw": password}
            )
            await conn.exec_driver_sql(str(statement))
            grants = (await conn.execute(_GRANTS, {"role": role})).one()
            for grant in grants:
                await conn.exec_driver_sql(str(grant))
    finally:
        await engine.dispose()
    return "updated" if existed else "created"
