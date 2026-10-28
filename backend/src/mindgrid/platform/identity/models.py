"""User and session tables. Both have row-level security: a user sees itself, a
superadmin sees everyone. Sign-in lookups before the actor is known go through the narrow
SECURITY DEFINER functions created in the migration."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


def _values(members: type[enum.StrEnum]) -> list[str]:
    """Store enum values (not member names) in the PostgreSQL enum type."""
    return [m.value for m in members]


class SystemRole(enum.StrEnum):
    SUPERADMIN = "superadmin"
    USER = "user"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Keyed, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", func.lower("email"), unique=True),)

    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role", values_callable=_values),
        default=SystemRole.USER,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=_values),
        default=UserStatus.ACTIVE,
    )
    locale: Mapped[str] = mapped_column(String(16), default="en")
    # Picture chosen from the web app's built-in set ("" = initials); never an upload.
    avatar: Mapped[str] = mapped_column(String(40), default="", server_default="")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Session(Keyed, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 hex
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str] = mapped_column(String(200), default="")


class UserGroup(Keyed, Base):
    """A named set of people; projects and categories give rights to the whole group."""

    __tablename__ = "user_groups"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserGroupMember(Base):
    __tablename__ = "user_group_members"
    __table_args__ = (Index("ix_user_group_members_user_id", "user_id"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
